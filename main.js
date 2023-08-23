// Description: main js file for the project
// code that handles input type="file" and shows the image
// summary: Send an image to create a viewer. Open a websocket. Update the viewer field as requested by the backend

console.log("starting main.js");

// define addresses
const ADDRESS = "127.0.0.1:8008";
const httpAddress = "http://" + ADDRESS;
const wsAddress = "ws://" + ADDRESS + "/ws";

// send reset request to backend
fetch(`${httpAddress}/reset`).then(response => response.json()).then(data => console.log(data));

// get button and main container
const fileInput = document.getElementById('fileUpload');
const container = document.getElementById('viewersContainer');
const kSlider = document.getElementById('kRange');
// kSlider max value should be always <= num clicks - 1
const threshSlider = document.getElementById('thresholdRange');
const euclideanDist = document.getElementById('euclidean');
// const cosineDist = document.getElementById('cosine');

var receivedKey = '';  // this key is used to know what is going to be next updated in the viewer and it's set by the backend
var viewersWs = new WebSocket(wsAddress + "/viewers");  // this websocket is used to receive images from the backend
viewersWs.onmessage = function(event) {
    console.log("message received")
    console.log(event.data)
    // decide if the message is key or image bytes
    // check if event.data is text
    if (typeof event.data === "string") {
        if (receivedKey === '') {
            // raise an error and exit
            receivedKey = event.data;
        } else {
            throw "Received key twice "
        }
    } else {
        // event.data is binary
        // check that key is received
        if (receivedKey === '') {
            throw "Received image before key "
        } else {
            // get viewer index and field from the response
            viewerIndex = receivedKey.split(',')[0];
            viewerField = receivedKey.split(',')[1];
            // get the viewer
            viewer = document.getElementById("viewer_" + viewerIndex);
            // get the canvas and context corresponding to the field
            if (viewerField === 'pimg') {
                canvas = viewer.imgCanvas;
                ctx = viewer.imgCtx;
            } else if (viewerField === 'prob') {
                canvas = viewer.probCanvas;
                ctx = viewer.probCtx;
            } else if (viewerField === 'mask') {
                canvas = viewer.maskCanvas;
                ctx = viewer.maskCtx;
            } else {
                throw "Received unknown field "
            }

            // now we can decode the image
            // create a new image
            var img = new Image();
            img.onload = function() {
                canvas.width = img.width;
                canvas.height = img.height;
                ctx.drawImage(img, 0, 0);
            };
            // write the image bytes to the image
            img.src = URL.createObjectURL(event.data);

            // reset the key
            receivedKey = '';
        }
    }
};




// create viewer class that will live inside container
class Viewer extends HTMLElement {
    constructor(index) {  // use an index to identify them
        super()
        this.index = index;
        // create a new viewer in container
        this.id = "viewer_" + index;
        // now create img, prob, mask canvases and make their contexts accessible
        this.imgCanvas = document.createElement('canvas', {id: this.id + "_img"});
        this.probCanvas = document.createElement('canvas', {id: this.id + "_prob"});
        this.maskCanvas = document.createElement('canvas', {id: this.id + "_mask"});
        // attach them to the viewer
        this.appendChild(this.imgCanvas); 
        this.appendChild(this.probCanvas);
        this.appendChild(this.maskCanvas);
        // get assciated contexts
        this.imgCtx = this.imgCanvas.getContext('2d');
        this.probCtx = this.probCanvas.getContext('2d');
        this.maskCtx = this.maskCanvas.getContext('2d');
    }
}
customElements.define("custom-viewer", Viewer);



// function that handles the input type="file"
async function handleFileSelect(event) {
    console.log("handleFileSelect");
    var files = event.target.files; // FileList object
    var file = files[0];
    // check that file is png or jpg
    if (!file.type.match('image.*')) {
        alert("File must be an image");
        return;
    }   
    // here we create a new viewer and add it to the container
    console.log("creating viewer")
    const viewer = new Viewer(container.childElementCount);
    container.appendChild(viewer);
    console.log('created viewer')
    console.log(viewer.id)
    console.log(container)

    // post the image to the backend
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${httpAddress}/newImg`, {
        method: 'POST',
        body: formData,
        })
    const response = await res.json();
    // add viewer to list of viewers

    console.log(response);
}
fileInput.addEventListener('change', handleFileSelect);

function postData (endpoint, key, value) {
    // send a post request with the new value
    fetch(`${httpAddress}/${endpoint}`, {
        method: 'POST',
        body: JSON.stringify({[key]: value}),
        headers: {
            'Content-Type': 'application/json'
        }
        })
    .then(response => response.json())
    .then(data => console.log(data)).catch(error => console.log(error));
}

// function that handles the k slider
kSlider.onchange = function() {
    value = kSlider.value;
    postData('setK', 'k', value);
}

threshSlider.onchange = function() {
    value = threshSlider.value;
    postData('setThresh', 'thresh', value);
}


euclideanDist.onchange = function() {
    if (euclideanDist.checked) {
        postData('setDist', 'dist', 'euclidean');
    }
}

// cosineDist.onchange = function() {
//     if (cosineDist.checked) {
//         postData('setDist', 'dist', 'cosine');
//     }
// }