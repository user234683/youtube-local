(function main() {
    /* Takes control of the form if javascript is enabled, so that adding stuff to a playlist will not cause things to stop loading, and will display a status message. If javascript is disabled, the form will still work using regular HTML methods, but causes things on the page (such as the video) to stop loading. */
    const playlistAddForm = document.getElementById('playlist-edit');

    function setStyle(element, property, value){
        element.style[property] = value;
    }
    function removeMessage(messageBox){
        messageBox.parentNode.removeChild(messageBox);
    }

    function displayMessage(text, error=false){
        let currentMessageBox = document.getElementById('message-box');
        if(currentMessageBox !== null){
            currentMessageBox.parentNode.removeChild(currentMessageBox);
        }
        let messageBox = document.createElement('div');
        if(error){
            messageBox.setAttribute('role', 'alert');
        } else {
            messageBox.setAttribute('role', 'status');
        }
        messageBox.setAttribute('id', 'message-box');
        let textNode = document.createTextNode(text);
        messageBox.appendChild(textNode);
        document.querySelector('main').appendChild(messageBox);
        let currentstyle = window.getComputedStyle(messageBox);
        let removalDelay;
        if(error){
            removalDelay = 5000;
        } else {
            removalDelay = 1500;
        }
        window.setTimeout(setStyle, 20, messageBox, 'opacity', 1);
        window.setTimeout(setStyle, removalDelay, messageBox, 'opacity', 0);
        window.setTimeout(removeMessage, removalDelay+300, messageBox);
    }
    // https://developer.mozilla.org/en-US/docs/Learn/HTML/Forms/Sending_forms_through_JavaScript
    function sendData(event){
        let clicked_button = document.activeElement;
        if(clicked_button === null || clicked_button.getAttribute('type') !== 'submit' || clicked_button.parentElement != event.target){
            console.log('ERROR: clicked_button not valid');
            return;
        }
        if(clicked_button.getAttribute('value') !== 'add'){
            return;     // video(s) are being removed from playlist, just let it refresh the page
        }
        event.preventDefault();
        let XHR = new XMLHttpRequest();
        let FD = new FormData(playlistAddForm);

        if(FD.getAll('video_info_list').length === 0){
            displayMessage('Error: No videos selected', true);
            return;
        }

        if(FD.get('playlist_name') === ""){
            displayMessage('Error: No playlist selected', true);
            return;
        }

        // https://stackoverflow.com/questions/48322876/formdata-doesnt-include-value-of-buttons
        FD.append('action', 'add');

        XHR.addEventListener('load', function(event){
            if(event.target.status == 204){
                displayMessage('Added videos to playlist "' + FD.get('playlist_name') + '"');
            } else {
                displayMessage('Error adding videos to playlist: ' + event.target.status.toString(), true);
            }
        });

        XHR.addEventListener('error', function(event){
            if(event.target.status == 0){
                displayMessage('XHR failed: Check that XHR requests are allowed', true);
            } else {
                displayMessage('XHR failed: Unknown error', true);
            }
        });

        XHR.open('POST', playlistAddForm.getAttribute('action'));
        XHR.send(FD);
    }

    playlistAddForm.addEventListener('submit', sendData);
}());
