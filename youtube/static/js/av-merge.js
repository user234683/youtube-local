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

// TODO: Call abort to cancel in-progress appends?



function AVMerge(video, srcInfo, startTime){
    this.audioSource = null;
    this.videoSource = null;
    this.avRatio = null;
    this.videoStream = null;
    this.audioStream = null;
    this.seeking = false;
    this.startTime = startTime;
    this.video = video;
    this.mediaSource = null;
    this.closed = false;
    this.opened = false;
    this.audioEndOfStreamCalled = false;
    this.videoEndOfStreamCalled = false;
    if (!('MediaSource' in window)) {
        reportError('MediaSource not supported.');
        return;
    }

    // Find supported video and audio sources
    for (var src of srcInfo['videos']) {
        if (MediaSource.isTypeSupported(src['mime_codec'])) {
            reportDebug('Using video source', src['mime_codec'],
                        src['quality_string'], 'itag', src['itag']);
            this.videoSource = src;
            break;
        }
    }
    for (var src of srcInfo['audios']) {
        if (MediaSource.isTypeSupported(src['mime_codec'])) {
            reportDebug('Using audio source', src['mime_codec'],
                        src['quality_string'], 'itag', src['itag']);
            this.audioSource = src;
            break;
        }
    }
    if (this.videoSource === null)
        reportError('No supported video MIME type or codec found: ',
                    srcInfo['videos'].map(s => s.mime_codec).join(', '));
    if (this.audioSource === null)
        reportError('No supported audio MIME type or codec found: ',
                    srcInfo['audios'].map(s => s.mime_codec).join(', '));
    if (this.videoSource === null || this.audioSource === null)
        return;

    if (this.videoSource.bitrate && this.audioSource.bitrate)
        this.avRatio = this.audioSource.bitrate/this.videoSource.bitrate;
    else
        this.avRatio = 1/10;

    this.setup();
}
AVMerge.prototype.setup = function() {
    this.mediaSource = new MediaSource();
    this.video.src = URL.createObjectURL(this.mediaSource);
    this.mediaSource.onsourceopen = this.sourceOpen.bind(this);
}

AVMerge.prototype.sourceOpen = function(_) {
    // If after calling mediaSource.endOfStream, the user seeks back
    // into the video, the sourceOpen event will be fired again. Do not
    // overwrite the streams.
    this.audioEndOfStreamCalled = false;
    this.videoEndOfStreamCalled = false;
    if (this.opened)
        return;
    this.opened = true;
    this.videoStream = new Stream(this, this.videoSource, this.startTime,
                                  this.avRatio);
    this.audioStream = new Stream(this, this.audioSource, this.startTime,
                                  this.avRatio);

    this.videoStream.setup();
    this.audioStream.setup();

    this.timeUpdateEvt = addEvent(this.video, 'timeupdate',
                                  this.checkBothBuffers.bind(this));
    this.seekingEvt = addEvent(this.video, 'seeking',
                               debounce(this.seek.bind(this), 500));
    //this.video.onseeked = function() {console.log('seeked')};
}
AVMerge.prototype.close = function() {
    if (this.closed)
        return;
    this.closed = true;
    this.videoStream.close();
    this.audioStream.close();
    this.timeUpdateEvt.remove();
    this.seekingEvt.remove();
    if (this.mediaSource.readyState == 'open')
        this.mediaSource.endOfStream();
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
        reportWarning('seek but not open? readyState:',
                      this.mediaSource.readyState);
    }
}
AVMerge.prototype.audioEndOfStream = function() {
    if (this.videoEndOfStreamCalled && !this.audioEndOfStreamCalled) {
        reportDebug('Calling mediaSource.endOfStream()');
        this.mediaSource.endOfStream();
    }
    this.audioEndOfStreamCalled = true;
}
AVMerge.prototype.videoEndOfStream = function() {
    if (this.audioEndOfStreamCalled && !this.videoEndOfStreamCalled) {
        reportDebug('Calling mediaSource.endOfStream()');
        this.mediaSource.endOfStream();
    }
    this.videoEndOfStreamCalled = true;
}
AVMerge.prototype.printDebuggingInfo = function() {
    reportDebug('videoSource:', this.videoSource);
    reportDebug('audioSource:', this.videoSource);
    reportDebug('video sidx:', this.videoStream.sidx);
    reportDebug('audio sidx:', this.audioStream.sidx);
    reportDebug('video updating', this.videoStream.sourceBuffer.updating);
    reportDebug('audio updating', this.audioStream.sourceBuffer.updating);
    reportDebug('video duration:', this.video.duration);
    reportDebug('video current time:', this.video.currentTime);
    reportDebug('mediaSource.readyState:', this.mediaSource.readyState);
    reportDebug('videoEndOfStreamCalled', this.videoEndOfStreamCalled);
    reportDebug('audioEndOfStreamCalled', this.audioEndOfStreamCalled);
    for (let obj of [this.videoStream, this.audioStream]) {
        reportDebug(obj.streamType, 'stream buffered times:');
        for (let i=0; i<obj.sourceBuffer.buffered.length; i++) {
            reportDebug(String(obj.sourceBuffer.buffered.start(i)) + '-'
                        + String(obj.sourceBuffer.buffered.end(i)));
        }
    }
}

function Stream(avMerge, source, startTime, avRatio) {
    this.avMerge = avMerge;
    this.video = avMerge.video;
    this.url = source['url'];
    this.ext = source['ext'];
    this.fileSize = source['file_size'];
    this.closed = false;
    this.mimeCodec = source['mime_codec']
    this.streamType = source['acodec'] ? 'audio' : 'video';
    if (this.streamType == 'audio') {
        this.bufferTarget = avRatio*50*10**6;
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
    this.updateendEvt = addEvent(this.sourceBuffer, 'updateend', (e) => {
        if (this.appendQueue.length != 0) {
            this.appendSegment(...this.appendQueue.shift());
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
            'Initialization+index segments',
        ).then(
            (buffer) => {
                var init_end = this.initRange.end - this.initRange.start + 1;
                var index_start = this.indexRange.start - this.initRange.start;
                var index_end = this.indexRange.end - this.initRange.start + 1;
                this.setupInitSegment(buffer.slice(0, init_end));
                this.setupSegmentIndex(buffer.slice(index_start, index_end));
            }
        );
    } else {
        // initialization data
        await fetchRange(
            this.url,
            this.initRange.start,
            this.initRange.end,
            'Initialization segment',
        ).then(this.setupInitSegment.bind(this));

        // sidx (segment index) table
        fetchRange(
            this.url,
            this.indexRange.start,
            this.indexRange.end,
            'Index segment',
        ).then(this.setupSegmentIndex.bind(this));
    }
}
Stream.prototype.setupInitSegment = function(initSegment) {
    if (this.ext == 'webm')
        this.sidx = extractWebmInitializationInfo(initSegment);
    this.appendSegment(null, initSegment);
}
Stream.prototype.setupSegmentIndex = async function(indexSegment){
    if (this.ext == 'webm') {
        this.sidx.entries = parseWebmCues(indexSegment, this.sidx);
        if (this.fileSize) {
            let lastIdx = this.sidx.entries.length - 1;
            this.sidx.entries[lastIdx].end = this.fileSize - 1;
        }
        for (let entry of this.sidx.entries) {
            entry.subSegmentDuration = entry.tickEnd - entry.tickStart + 1;
            if (entry.end)
                entry.referencedSize = entry.end - entry.start + 1;
        }
    } else {
        var box = unbox(indexSegment);
        this.sidx = sidx_parse(box.data, this.indexRange.end+1);
    }
    this.fetchSegmentIfNeeded(this.getSegmentIdx(this.startTime));
}
Stream.prototype.close = function() {
    // Prevents appendSegment adding to buffer if request finishes
    // after closing
    this.closed = true;
    if (this.sourceBuffer.updating)
        this.sourceBuffer.abort();
    this.mediaSource.removeSourceBuffer(this.sourceBuffer);
    this.updateendEvt.remove();
}
Stream.prototype.appendSegment = function(segmentIdx, chunk) {
    if (this.closed)
        return;

    this.reportDebug('Received segment', segmentIdx)

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
        this.reportWarning('QuotaExceededError.');

        // Count how many bytes are in buffer to update buffering target,
        // updating .have as well for when we need to delete segments
        var bytesInBuffer = 0;
        for (var i = 0; i < this.sidx.entries.length; i++) {
            if (this.segmentInBuffer(i))
                bytesInBuffer += this.sidx.entries[i].referencedSize;
            else if (this.sidx.entries[i].have) {
                this.sidx.entries[i].have = false;
                this.sidx.entries[i].requested = false;
            }
        }
        bytesInBuffer = Math.floor(4/5*bytesInBuffer);
        if (bytesInBuffer < this.bufferTarget) {
            this.bufferTarget = bytesInBuffer;
            this.reportDebug('New buffer target:', this.bufferTarget);
        }

        // Delete 10 segments (arbitrary) from buffer, making sure
        // not to delete current one
        var currentSegment = this.getSegmentIdx(this.video.currentTime);
        var numDeleted = 0;
        var i = 0;
        const DELETION_TARGET = 10;
        var toDelete = []; // See below for why we have to schedule it
        this.reportDebug('Deleting segments from beginning of buffer.');
        while (numDeleted < DELETION_TARGET && i < currentSegment) {
            if (this.sidx.entries[i].have) {
                toDelete.push(i)
                numDeleted++;
            }
            i++;
        }
        if (numDeleted < DELETION_TARGET)
            this.reportDebug('Deleting segments from end of buffer.');

        i = this.sidx.entries.length - 1;
        while (numDeleted < DELETION_TARGET && i > currentSegment) {
            if (this.sidx.entries[i].have) {
                toDelete.push(i)
                numDeleted++;
            }
            i--;
        }

        // When calling .remove, the sourceBuffer will go into updating=true
        // state, and remove cannot be called until it is done. So we have
        // to delete on the updateend event for subsequent ones.
        var removeFinishedEvent;
        var deletedStuff = (toDelete.length !== 0)
        var deleteSegment = () => {
            if (toDelete.length === 0) {
                removeFinishedEvent.remove();
                // If QuotaExceeded happened for current segment, retry the
                // append
                // Rescheduling will take care of updating=true problem.
                // Also check that we found segments to delete, to avoid
                // infinite looping if we can't delete anything
                if (segmentIdx === currentSegment && deletedStuff) {
                    this.reportDebug('Retrying appendSegment for', segmentIdx);
                    this.appendSegment(segmentIdx, chunk);
                } else {
                    this.reportDebug('Not retrying segment', segmentIdx);
                    this.sidx.entries[segmentIdx].requested = false;
                }
                return;
            }
            let idx = toDelete.shift();
            let entry = this.sidx.entries[idx];
            let start = entry.tickStart/this.sidx.timeScale;
            let end = (entry.tickEnd+1)/this.sidx.timeScale;
            this.reportDebug('Deleting segment', idx);
            this.sourceBuffer.remove(start, end);
            entry.have = false;
            entry.requested = false;
        }
        removeFinishedEvent = addEvent(this.sourceBuffer, 'updateend',
                                       deleteSegment);
        if (!this.sourceBuffer.updating)
            deleteSegment();
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
        if (entry.tickStart <= currentTick && (entry.tickEnd+1) > currentTick){
            return index;
        }
        index = index + increment;
    }
    this.reportError('Could not find segment index for time', videoTime);
    return 0;
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
    // We have all the segments until the end
    // Signal the end of stream
    } else if (i == this.sidx.entries.length) {
        if (this.streamType == 'audio')
            this.avMerge.audioEndOfStream();
        else
            this.avMerge.videoEndOfStream();
    }
}
Stream.prototype.segmentInBuffer = function(segmentIdx) {
    var entry = this.sidx.entries[segmentIdx];
    // allow for 0.01 second error
    var timeStart = entry.tickStart/this.sidx.timeScale + 0.01;

    /* Some of YouTube's mp4 fragments are malformed, with half-frame
    playback gaps. In this video at 240p (timeScale = 90000 ticks/second)
        https://www.youtube.com/watch?v=ZhOQCwJvwlo
    segment 4 (starting at 0) is claimed in the sidx table to have
    a duration of 388500 ticks, but closer examination of the file using
    Bento4 mp4dump shows that the segment has 129 frames at 3000 ticks
    per frame, which gives an actual duration of 38700 (1500 less than
    claimed). The file is 30 fps, so this error is exactly half a frame.

    Note that the base_media_decode_time exactly matches the tickStart,
    so the media decoder is being given a time gap of half a frame.

    The practical result of this is that sourceBuffer.buffered reports
    a timeRange.end that is less than expected for that segment, resulting in
    a false determination that the browser has deleted a segment.

    Segment 5 has the opposite issue, where it has a 1500 tick surplus of video
    data compared to the sidx length. Segments 6 and 7 also have this
    deficit-surplus pattern.

    This might have something to do with the fact that the video also
    has 60 fps formats. In order to allow for adaptive streaming and seamless
    quality switching, YouTube likely encodes their formats to line up nicely.
    Either there is a bug in their encoder, or this is intentional. Allow for
    up to 1 frame-time of error to work around this issue. */
    if (this.streamType == 'video')
        var endError = 1/(this.avMerge.videoSource.fps || 30);
    else
        var endError = 0.01
    var timeEnd = (entry.tickEnd+1)/this.sidx.timeScale - endError;

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
    this.reportDebug(
        'Fetching segment', segmentIdx, ', bytes',
        entry.start, entry.end, ', seconds',
        entry.tickStart/this.sidx.timeScale,
        (entry.tickEnd+1)/this.sidx.timeScale
    )
    fetchRange(
        this.url,
        entry.start,
        entry.end,
        String(this.streamType) + ' segment ' + String(segmentIdx),
    ).then(this.appendSegment.bind(this, segmentIdx));
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
Stream.prototype.handleSeek = function() {
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

// https://gomakethings.com/promise-based-xhr/
// https://stackoverflow.com/a/30008115
// http://lofi.limo/blog/retry-xmlhttprequest-carefully
function fetchRange(url, start, end, debugInfo) {
    return new Promise((resolve, reject) => {
        var retryCount = 0;
        var xhr = new XMLHttpRequest();
        function onFailure(err, message, maxRetries=5){
            message = debugInfo + ': ' + message + ' - Err: ' + String(err);
            retryCount++;
            if (retryCount > maxRetries || xhr.status == 403){
                reportError('fetchRange error while fetching ' + message);
                reject(message);
                return;
            } else {
                reportWarning('Failed to fetch ' + message
                    + '. Attempting retry '
                    + String(retryCount) +'/' + String(maxRetries));
            }

            // Retry in 1 second, doubled for each next retry
            setTimeout(function(){
                xhr.open('get',url);
                xhr.send();
            }, 1000*Math.pow(2,(retryCount-1)));
        }
        xhr.open('get', url);
        xhr.timeout = 15000;
        xhr.responseType = 'arraybuffer';
        xhr.setRequestHeader('Range', 'bytes=' + start + '-' + end);
        xhr.onload = function (e) {
            if (xhr.status >= 200 && xhr.status < 300) {
                resolve(xhr.response);
            } else {
                onFailure(e, 
                    'Status '
                    + String(xhr.status) + ' ' + String(xhr.statusText)
                );
            }
        };
        xhr.onerror = function (event) {
            onFailure(e, 'Network error');
        };
        xhr.ontimeout = function (event){
            xhr.timeout += 5000;
            onFailure(null, 'Timeout (15s)', maxRetries=5);
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

// allow to remove an event listener without having a function reference
function RegisteredEvent(obj, eventName, func) {
    this.obj = obj;
    this.eventName = eventName;
    this.func = func;
    obj.addEventListener(eventName, func);
}
RegisteredEvent.prototype.remove = function() {
    this.obj.removeEventListener(this.eventName, this.func);
}
function addEvent(obj, eventName, func) {
    return new RegisteredEvent(obj, eventName, func);
}

function reportWarning(...args){
    console.warn(...args);
}
function reportError(...args){
    console.error(...args);
}
function reportDebug(...args){
    console.debug(...args);
}

function byteArrayToIntegerLittleEndian(unsignedByteArray){
    var result = 0;
    for (byte of unsignedByteArray){
        result = result*256;
        result += byte
    }
    return result;
}
function byteArrayToFloat(byteArray) {
    var view = new DataView(byteArray.buffer);
    if (byteArray.length == 4)
        return view.getFloat32(byteArray.byteOffset);
    else
        return view.getFloat64(byteArray.byteOffset);
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


function extractWebmInitializationInfo(initializationSegment) {
    var result = {
        timeScale: null,
        cuesOffset: null,
        duration: null,
    };
    (new EbmlDecoder()).readTags(initializationSegment, (tagType, tag) => {
        if (tag.name == 'TimecodeScale')
            result.timeScale = byteArrayToIntegerLittleEndian(tag.data);
        else if (tag.name == 'Duration')
            // Integer represented as a float (why??); units of TimecodeScale
            result.duration = byteArrayToFloat(tag.data);
        // https://lists.matroska.org/pipermail/matroska-devel/2013-July/004549.html
        // "CueClusterPosition in turn is relative to the segment's data start
        // position" (the data start is the position after the bytes
        // used to represent the tag ID and entry size)
        else if (tagType == 'start' && tag.name == 'Segment')
            result.cuesOffset = tag.dataStart;
    });
    if (result.timeScale === null) {
        result.timeScale = 1000000;
    }

    // webm timecodeScale is the number of nanoseconds in a tick
    // Convert it to number of ticks per second to match mp4 convention
    result.timeScale = 10**9/result.timeScale;
    return result;
}
function parseWebmCues(indexSegment, initInfo) {
    var entries = [];
    var currentEntry = {};
    var cuesOffset = initInfo.cuesOffset;
    (new EbmlDecoder()).readTags(indexSegment, (tagType, tag) => {
        if (tag.name == 'CueTime') {
            const tickStart = byteArrayToIntegerLittleEndian(tag.data);
            currentEntry.tickStart = tickStart;
            if (entries.length !== 0)
                entries[entries.length - 1].tickEnd = tickStart - 1;
        } else if (tag.name == 'CueClusterPosition') {
            const byteStart = byteArrayToIntegerLittleEndian(tag.data);
            currentEntry.start = cuesOffset + byteStart;
            if (entries.length !== 0)
                entries[entries.length - 1].end = cuesOffset + byteStart - 1;
        } else if (tagType == 'end' && tag.name == 'CuePoint') {
            entries.push(currentEntry);
            currentEntry = {};
        }
    });
    if (initInfo.duration)
        entries[entries.length - 1].tickEnd = initInfo.duration - 1;
    return entries;
}

// BEGIN node-ebml (modified) for parsing WEBM cues table
// https://github.com/node-ebml/node-ebml

/* Copyright (c) 2013-2018 Mark Schmale and contributors

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
of the Software, and to permit persons to whom the Software is furnished to do
so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.*/

const schema = new Map([
    [0x18538067, ['Segment', 'm']],
    [0x1c53bb6b, ['Cues', 'm']],
    [0xbb, ['CuePoint', 'm']],
    [0xb3, ['CueTime', 'u']],
    [0xb7, ['CueTrackPositions', 'm']],
    [0xf7, ['CueTrack', 'u']],
    [0xf1, ['CueClusterPosition', 'u']],
    [0x1549a966, ['Info', 'm']],
    [0x2ad7b1, ['TimecodeScale', 'u']],
    [0x4489, ['Duration', 'f']],
]);


function EbmlDecoder() {
    this.buffer = null;
    this.emit = null;
    this.tagStack = [];
    this.cursor = 0;
}
EbmlDecoder.prototype.readTags = function(chunk, onParsedTag) {
    this.buffer = new Uint8Array(chunk);
    this.emit = onParsedTag;

    while (this.cursor < this.buffer.length) {
        if (!this.readTag() || !this.readSize() || !this.readContent()) {
            break;
        }
    }
}
EbmlDecoder.prototype.getSchemaInfo = function(tag) {
    if (Number.isInteger(tag) && schema.has(tag)) {
        var name, type;
        [name, type] = schema.get(tag);
        return {name, type};
    }
    return {
        type: null,
        name: 'unknown',
    };
}
EbmlDecoder.prototype.readTag = function() {
    if (this.cursor >= this.buffer.length) {
        return false;
    }

    const tag = readVint(this.buffer, this.cursor);
    if (tag == null) {
        return false;
    }

    const tagObj = {
        tag: tag.value,
        ...this.getSchemaInfo(tag.valueWithLeading1),
        start: this.cursor,
        end: this.cursor + tag.length,  // exclusive; also overwritten below
    };
    this.tagStack.push(tagObj);

    this.cursor += tag.length;
    return true;
}
EbmlDecoder.prototype.readSize = function() {
    const tagObj = this.tagStack[this.tagStack.length - 1];

    if (this.cursor >= this.buffer.length) {
        return false;
    }

    const size = readVint(this.buffer, this.cursor);
    if (size == null) {
        return false;
    }

    tagObj.dataSize = size.value;

    // unknown size
    if (size.value === -1) {
        tagObj.end = -1;
    } else {
        tagObj.end += size.value + size.length;
    }

    this.cursor += size.length;
    tagObj.dataStart = this.cursor;
    return true;
}
EbmlDecoder.prototype.readContent = function() {
    const { type, dataSize, ...rest } = this.tagStack[
        this.tagStack.length - 1
    ];

    if (type === 'm') {
        this.emit('start', { type, dataSize, ...rest });
        return true;
    }

    if (this.buffer.length < this.cursor + dataSize) {
        return false;
    }

    const data = this.buffer.subarray(this.cursor, this.cursor + dataSize);
    this.cursor += dataSize;

    this.tagStack.pop(); // remove the object from the stack

    this.emit('tag', { type, dataSize, data, ...rest });

    while (this.tagStack.length > 0) {
        const topEle = this.tagStack[this.tagStack.length - 1];
        if (this.cursor < topEle.end) {
            break;
        }
        this.emit('end', topEle);
        this.tagStack.pop();
    }
    return true;
}


// user234683 notes: The matroska variable integer format is as follows:
// The first byte is where the length of the integer in bytes is determined.
// The number of bytes for the integer is equal to the number of leading
// zeroes in that first byte PLUS 1. Then there is a single 1 bit separator,
// and the rest of the bits in the first byte and the rest of the bits in
// the subsequent bytes are the value of the number. Note the 1-bit separator
// is not part of the value, but by convention IS included in the value for the
// EBML Tag IDs in the schema table above
// The byte-length includes the first byte. So one could also say the number
// of leading zeros is the number of subsequent bytes to include.
function readVint(buffer, start = 0) {
    const length = 8 - Math.floor(Math.log2(buffer[start]));

    if (start + length > buffer.length) {
        return null;
    }

    let value = buffer[start] & ((1 << (8 - length)) - 1);
    let valueWithLeading1 = buffer[start] & ((1 << (8 - length + 1)) - 1);
    for (let i = 1; i < length; i += 1) {
        // user234683 notes: Bails out with -1 (unknown) if the value would
        // exceed 53 bits, which is the limit since JavaScript stores all
        // numbers as floating points. See
        // https://github.com/node-ebml/node-ebml/issues/49
        if (i === 7) {
            if (value >= 2 ** 8 && buffer[start + 7] > 0) {
                return { length, value: -1, valueWithLeading1: -1 };
            }
        }
        value *= 2 ** 8;
        value += buffer[start + i];
        valueWithLeading1 *= 2 ** 8;
        valueWithLeading1 += buffer[start + i];
    }

    return { length, value, valueWithLeading1 };
}
// END node-ebml
