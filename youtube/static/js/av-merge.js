// Heavily modified from
// https://github.com/nickdesaulniers/netfix/issues/4#issuecomment-578856471
// which was in turn modified from
// https://github.com/nickdesaulniers/netfix/blob/gh-pages/demo/bufferWhenNeeded.html

// Useful reading:
// https://stackoverflow.com/questions/35177797/what-exactly-is-fragmented-mp4fmp4-how-is-it-different-from-normal-mp4
// https://axel.isouard.fr/blog/2016/05/24/streaming-webm-video-over-html5-with-media-source

// We start by parsing the sidx (segment index) table in order to get the
// byte ranges of the segments. The byte range of the sidx table is provided
// by the indexRange variable by YouTube

// Useful info, as well as segments vs sequence mode (we use segments mode)
// https://joshuatz.com/posts/2020/appending-videos-in-javascript-with-mediasource-buffers/

// SourceBuffer data limits:
// https://developers.google.com/web/updates/2017/10/quotaexceedederror

// TODO: AVMerge.close()
// TODO: close stream at end?
// TODO: Better buffering algorithm
// TODO: Call abort to cancel in-progress appends?


var avMerge;

function avInitialize(...args){
    avMerge = new AVMerge(...args);
}

function AVMerge(video, srcPair, startTime){
    this.videoSource = srcPair[0];
    this.audioSource = srcPair[1];
    this.videoStream = null;
    this.audioStream = null;
    this.seeking = false;
    this.startTime = startTime;
    this.video = video;
    this.mediaSource = null;
    this.setup();
}
AVMerge.prototype.setup = function() {
    if ('MediaSource' in window
            && MediaSource.isTypeSupported(this.audioSource['mime_codec'])
            && MediaSource.isTypeSupported(this.videoSource['mime_codec'])) {
        this.mediaSource = new MediaSource();
        this.video.src = URL.createObjectURL(this.mediaSource);
        this.mediaSource.onsourceopen = this.sourceOpen.bind(this);
    } else {
        reportError('Unsupported MIME type or codec: ',
                    this.audioSource['mime_codec'],
                    this.videoSource['mime_codec']);
    }
}

AVMerge.prototype.sourceOpen = function(_) {
    this.videoStream = new Stream(this, this.videoSource, this.startTime);
    this.audioStream = new Stream(this, this.audioSource, this.startTime);

    this.videoStream.setup();
    this.audioStream.setup();

    this.video.ontimeupdate = this.checkBothBuffers.bind(this);
    this.video.onseeking = debounce(this.seek.bind(this), 500);
    //this.video.onseeked = function() {console.log('seeked')};
}
AVMerge.prototype.checkBothBuffers = function() {
    this.audioStream.checkBuffer();
    this.videoStream.checkBuffer();
}
AVMerge.prototype.seek = function(e) {
    if (this.mediaSource.readyState === 'open') {
        this.seeking = true;
        this.audioStream.handleSeek();
        this.videoStream.handleSeek();
        this.seeking = false;
    } else {
        this.reportWarning('seek but not open? readyState:',
                           this.mediaSource.readyState);
    }
}

function Stream(avMerge, source, startTime) {
    this.avMerge = avMerge;
    this.video = avMerge.video;
    this.url = source['url'];
    this.mimeCodec = source['mime_codec']
    this.streamType = source['acodec'] ? 'audio' : 'video';
    if (this.streamType == 'audio') {
        this.bufferTarget = 5*10**6; // 5 megabytes
    } else {
        this.bufferTarget = 50*10**6; // 50 megabytes
    }

    this.initRange = source['init_range'];
    this.indexRange = source['index_range'];

    this.startTime = startTime;
    this.mediaSource = avMerge.mediaSource;
    this.sidx = null;
    this.appendRetries = 0;
    this.appendQueue = []; // list of [segmentIdx, data]
    this.sourceBuffer = this.mediaSource.addSourceBuffer(this.mimeCodec);
    this.sourceBuffer.mode = 'segments';
    this.sourceBuffer.addEventListener('error', (e) => {
        this.reportError('sourceBuffer error', e);
    });
    this.sourceBuffer.addEventListener('updateend', (e) => {
        this.reportDebug('updateend', e);
        if (this.appendQueue.length != 0) {
            this.appendSegment(...this.appendQueue.pop());
        }
    });
}
Stream.prototype.setup = async function(){
    // Group requests together
    if (this.initRange.end+1 == this.indexRange.start){
        fetchRange(
            this.url,
            this.initRange.start,
            this.indexRange.end,
            (buffer) => {
                var init_end = this.initRange.end - this.initRange.start + 1;
                var index_start = this.indexRange.start - this.initRange.start;
                var index_end = this.indexRange.end - this.initRange.start + 1;
                this.appendSegment(null, buffer.slice(0, init_end));
                this.setupSegments(buffer.slice(index_start, index_end));
            }
        )
    } else {
        // initialization data
        await fetchRange(
            this.url,
            this.initRange.start,
            this.initRange.end,
            this.appendSegment.bind(this, null),
        );
        // sidx (segment index) table
        fetchRange(
            this.url,
            this.indexRange.start,
            this.indexRange.end,
            this.setupSegments.bind(this)
        );
    }
}
Stream.prototype.setupSegments = async function(sidxBox){
    var box = unbox(sidxBox);
    this.sidx = sidx_parse(box.data, this.indexRange.end+1);
    this.reportDebug('sidx', this.sidx);

    this.reportDebug('appending first segment');
    this.fetchSegmentIfNeeded(this.getSegmentIdx(this.startTime));
}
Stream.prototype.appendSegment = function(segmentIdx, chunk) {
    // cannot append right now, schedule for updateend
    if (this.sourceBuffer.updating) {
        this.reportDebug('sourceBuffer updating, queueing for later');
        this.appendQueue.push([segmentIdx, chunk]);
        if (this.appendQueue.length > 2){
            this.reportWarning('appendQueue length:', this.appendQueue.length);
        }
        return;
    }
    try {
        this.sourceBuffer.appendBuffer(chunk);
        if (segmentIdx !== null)
            this.sidx.entries[segmentIdx].have = true;
        this.appendRetries = 0;
    } catch (e) {
        if (e.name !== 'QuotaExceededError') {
            throw e;
        }
        // Delete 3 segments (arbitrary) from beginning of buffer, making sure
        // not to delete current one
        var currentSegment = this.getSegmentIdx(this.video.currentTime);
        this.reportDebug('QuotaExceededError. Deleting segments.');
        var numDeleted = 0;
        var i = 0;
        while (numDeleted < 3 && i < currentSegment) {
            let entry = this.sidx.entries[i];
            let start = entry.tickStart/this.sidx.timeScale;
            let end = entry.tickEnd/this.sidx.timeScale;
            if (entry.have) {
                this.reportDebug('Deleting segment', i);
                this.sourceBuffer.remove(start, end);
            }
        }
    }
}
Stream.prototype.getSegmentIdx = function(videoTime) {
    // get an estimate
    var currentTick = videoTime * this.sidx.timeScale;
    var firstSegmentDuration = this.sidx.entries[0].subSegmentDuration;
    var index = 1 + Math.floor(currentTick / firstSegmentDuration);
    var index = clamp(index, 0, this.sidx.entries.length - 1);

    var increment = 1;
    if (currentTick < this.sidx.entries[index].tickStart){
        increment = -1;
    }

    // go up or down to find correct index
    while (index >= 0 && index < this.sidx.entries.length) {
        var entry = this.sidx.entries[index];
        if (entry.tickStart <= currentTick && entry.tickEnd >= currentTick){
            return index;
        }
        index = index + increment;
    }
    this.reportError('Could not find segment index for time', videoTime);
    return 0;
}
Stream.prototype.shouldFetchNextSegment = function(nextSegment) {
    // > 15% done with current segment
    if (nextSegment >= this.sidx.entries.length){
        return false;
    }
    var entry = this.sidx.entries[nextSegment - 1];
    var currentTick = this.video.currentTime * this.sidx.timeScale;
    return currentTick > (entry.tickStart + entry.subSegmentDuration*0.15);
}
Stream.prototype.checkBuffer = async function() {
    if (this.avMerge.seeking) {
        return;
    }
    // Find the first unbuffered segment, i
    var currentSegmentIdx = this.getSegmentIdx(this.video.currentTime);
    var bufferedBytesAhead = 0;
    var i;
    for (i = currentSegmentIdx; i < this.sidx.entries.length; i++) {
        var entry = this.sidx.entries[i];
        // check if we had it before, but it was deleted by the browser
        if (entry.have && !this.segmentInBuffer(i)) {
            this.reportDebug('segment', i, 'deleted by browser');
            entry.have = false;
            entry.requested = false;
        }
        if (!entry.have) {
            break;
        }
        bufferedBytesAhead += entry.referencedSize;
        if (bufferedBytesAhead > this.bufferTarget) {
            return;
        }
    }

    if (i < this.sidx.entries.length && !this.sidx.entries[i].requested) {
        this.fetchSegment(i);
    }
}
Stream.prototype.segmentInBuffer = function(segmentIdx) {
    var entry = this.sidx.entries[segmentIdx];
    // allow for 0.01 second error
    var timeStart = entry.tickStart/this.sidx.timeScale + 0.01;
    var timeEnd = entry.tickEnd/this.sidx.timeScale - 0.01;
    var timeRanges = this.sourceBuffer.buffered;
    for (var i=0; i < timeRanges.length; i++) {
        if (timeRanges.start(i) <= timeStart && timeEnd <= timeRanges.end(i)) {
            return true;
        }
    }
    return false;
}
Stream.prototype.fetchSegment = function(segmentIdx) {
    entry = this.sidx.entries[segmentIdx];
    entry.requested = true;
    fetchRange(
        this.url,
        entry.start,
        entry.end,
        this.appendSegment.bind(this, segmentIdx),
    );
}
Stream.prototype.fetchSegmentIfNeeded = function(segmentIdx) {
    if (segmentIdx < 0 || segmentIdx >= this.sidx.entries.length){
        return;
    }
    entry = this.sidx.entries[segmentIdx];
    // check if we had it before, but it was deleted by the browser
    if (entry.have && !this.segmentInBuffer(segmentIdx)) {
        this.reportDebug('segment', segmentIdx, 'deleted by browser');
        entry.have = false;
        entry.requested = false;
    }
    if (entry.requested) {
        return;
    }

    this.fetchSegment(segmentIdx);
}
Stream.prototype.handleSeek = async function() {
    var segmentIdx = this.getSegmentIdx(this.video.currentTime);
    this.fetchSegmentIfNeeded(segmentIdx);
}
Stream.prototype.reportDebug = function(...args) {
    reportDebug(String(this.streamType) + ':', ...args);
}
Stream.prototype.reportWarning = function(...args) {
    reportWarning(String(this.streamType) + ':', ...args);
}
Stream.prototype.reportError = function(...args) {
    reportError(String(this.streamType) + ':', ...args);
}


// Utility functions
function fetchRange(url, start, end, cb) {
    reportDebug('fetchRange', start, end);
    return new Promise((resolve, reject) => {
        var xhr = new XMLHttpRequest();
        xhr.open('get', url);
        xhr.responseType = 'arraybuffer';
        xhr.setRequestHeader('Range', 'bytes=' + start + '-' + end);
        xhr.onload = function() {
            reportDebug('fetched bytes: ', start, end);
            //bytesFetched += end - start + 1;
            resolve(cb(xhr.response));
        };
        xhr.send();
    });
}

function debounce(func, wait, immediate) {
    var timeout;
    return function() {
        var context = this;
        var args = arguments;
        var later = function() {
            timeout = null;
            if (!immediate) func.apply(context, args);
        };
        var callNow = immediate && !timeout;
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
        if (callNow) func.apply(context, args);
    };
}

function clamp(number, min, max) {
  return Math.max(min, Math.min(number, max));
}

function reportWarning(...args){
    console.log(...args);
}
function reportError(...args){
    console.log(...args);
}
function reportDebug(...args){
    console.log(...args);
}

function byteArrayToIntegerLittleEndian(unsignedByteArray){
    var result = 0;
    for (byte of unsignedByteArray){
        result = result*256;
        result += byte
    }
    return result;
}
function ByteParser(data){
    this.curIndex = 0;
    this.data = new Uint8Array(data);
}
ByteParser.prototype.readInteger = function(nBytes){
    var result = byteArrayToIntegerLittleEndian(
        this.data.slice(this.curIndex, this.curIndex + nBytes)
    );
    this.curIndex += nBytes;
    return result;
}
ByteParser.prototype.readBufferBytes = function(nBytes){
    var result = this.data.slice(this.curIndex, this.curIndex + nBytes);
    this.curIndex += nBytes;
    return result;
}

// BEGIN iso-bmff-parser-stream/lib/box/sidx.js (modified)
// https://github.com/necccc/iso-bmff-parser-stream/blob/master/lib/box/sidx.js
/* The MIT License (MIT)

Copyright (c) 2014 Szabolcs Szabolcsi-Toth

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.*/
function sidx_parse (data, offset) {
	var bp = new ByteParser(data),
		version = bp.readInteger(1),
		flags = bp.readInteger(3),
		referenceId = bp.readInteger(4),
		timeScale = bp.readInteger(4),
		earliestPresentationTime = bp.readInteger(version === 0 ? 4 : 8),
		firstOffset = bp.readInteger(4),
		__reserved = bp.readInteger(2),
		entryCount = bp.readInteger(2),
		entries = [];

    var totalBytesOffset = firstOffset + offset;
    var totalTicks = 0;
	for (var i = entryCount; i > 0; i=i-1 ) {
        let referencedSize = bp.readInteger(4),
			subSegmentDuration = bp.readInteger(4),
			unused = bp.readBufferBytes(4)
		entries.push({
			referencedSize: referencedSize,
			subSegmentDuration: subSegmentDuration,
			unused: unused,
            start: totalBytesOffset,
            end: totalBytesOffset + referencedSize - 1, // inclusive
            tickStart: totalTicks,
            tickEnd: totalTicks + subSegmentDuration - 1,
            requested: false,
            have: false,
		});
        totalBytesOffset = totalBytesOffset + referencedSize;
        totalTicks = totalTicks + subSegmentDuration;
	}

	return {
		version: version,
		flags: flags,
		referenceId: referenceId,
		timeScale: timeScale,
		earliestPresentationTime: earliestPresentationTime,
		firstOffset: firstOffset,
		entries: entries
	};
}
// END sidx.js

// BEGIN iso-bmff-parser-stream/lib/unbox.js (same license), modified
function unbox(buf) {
	var bp = new ByteParser(buf),
		bufferLength = buf.length,
		length,
		typeData,
		boxData

    length = bp.readInteger(4); // length of entire box,
    typeData = bp.readInteger(4);

    if (bufferLength - length < 0) {
        reportWarning('Warning: sidx table is cut off');
        return {
            currentLength: bufferLength,
            length: length,
            type: typeData,
            data: bp.readBufferBytes(bufferLength)
        };
    }

    boxData = bp.readBufferBytes(length - 8);

    return {
        length: length,
        type: typeData,
        data: boxData
    };
}
// END unbox.js
