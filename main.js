// Description: main js file for the project
// code that handles input type="file" and shows the image
// summary: Send an image to create a viewer. Open a websocket. Update the viewer field as requested by the backend

console.log("starting main.js");

// define addresses
const ADDRESS = "138.231.63.90:2332";
const httpAddress = "http://" + ADDRESS;
const wsAddress = "ws://" + ADDRESS + "/ws";

// send reset request to backend
fetch(`${httpAddress}/reset`).then(response => response.json()).then(data => console.log(data));

// get button and main container
const fileInput = document.getElementById('fileUpload');
const container = document.getElementById('viewersContainer');
const kSlider = document.getElementById('kRange');
// kSlider max value should be always <= num clicks - 1
//const threshSlider = document.getElementById('thresholdRange');
const euclideanDist = document.getElementById('euclidean');


// const cosineDist = document.getElementById('cosine');
var clicks = [];  // list of clicks
// every time clicks is updated we change the max of kslider
    
var receivedKey = '';  // this key is used to know what is going to be next updated in the viewer and it's set by the backend
var viewersWs = new WebSocket(wsAddress + "/viewers");  // this websocket is used to receive images from the backend
viewersWs.onmessage = function(event) {
    console.log("message received")
    // decide if the message is key or image bytes
    // check if event.data is text
    if (typeof event.data === "string") {
        if (receivedKey === '') {
            receivedKey = event.data;
            console.log('received key:' + receivedKey)
        } else {
            // raise an error and exit
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
                console.log('setting pimg...')
                writeImage(viewer.imgCanvas, viewer.imgCtx, event.data)
            } else if (viewerField === 'prob') {
                console.log('setting prob...')
                writeImage(viewer.probCanvas, viewer.probCtx, event.data)
            } else if (viewerField === 'mask') {
                console.log('setting mask...')
                writeImageAndAnother(viewer.maskCanvas, viewer.maskCtx, event.data, viewer.imgCanvas)
            } else {
                throw "Received unknown field "
            }
            viewer.renderDisplay();


            console.log('set!')

            // reset the key
            receivedKey = '';
        }
    }
};

function writeImage(canvas, ctx, data) {
    // create a new image
    var img = new Image();
    img.onload = function() {
        canvas.width = img.width;
        canvas.height = img.height;
        ctx.drawImage(img, 0, 0);
    };
    // write the image bytes to the image
    img.src = URL.createObjectURL(data);
}

function writeImageAndAnother(canvas, ctx, data, anotherCanvas) {
    // create a new image
    var img = new Image();
    img.onload = function() {
        canvas.width = img.width;
        canvas.height = img.height;
        ctx.globalAlpha = 1;
        ctx.drawImage(img, 0, 0);
        ctx.globalAlpha = 0.5;
        ctx.drawImage(anotherCanvas, 0, 0);
    };
    // write the image bytes to the image
    img.src = URL.createObjectURL(data);
}




// create viewer class that will live inside container
class Viewer extends HTMLElement {
    constructor(index) {  // use an index to identify them
        super()
        this.index = index;
        // create a new viewer in container
        this.id = "viewer_" + index;
        // now create img, prob, mask canvases and make their contexts accessible
        this.displayCanvas = document.createElement('canvas', {id: this.id + "_display"});
        this.imgCanvas = document.createElement('canvas', {id: this.id + "_img"});
        this.probCanvas = document.createElement('canvas', {id: this.id + "_prob"});
        this.maskCanvas = document.createElement('canvas', {id: this.id + "_mask"});
        // attach them to the viewer
        this.appendChild(this.displayCanvas); 
        // this.appendChild(this.imgCanvas); 
        this.appendChild(this.probCanvas);
        this.appendChild(this.maskCanvas);
        // get assciated contexts
        this.displayCtx = this.displayCanvas.getContext('2d');
        this.imgCtx = this.imgCanvas.getContext('2d');
        this.probCtx = this.probCanvas.getContext('2d');
        this.maskCtx = this.maskCanvas.getContext('2d');

        this.displayCanvas.addEventListener('click', this.handleClick.bind(this));
        this.displayCanvas.addEventListener('contextmenu', this.handleClick.bind(this));
    }

    // define the behavior when a click is added into the image
    handleClick = function(event) {
        event.preventDefault();
        if (event.button == 0) {
            var isPositive = true;
        } else if (event.button == 2) {
            var isPositive = false;
        } else {
            return
        }
        // get the click coordinates in pixels
        var x = event.offsetX;
        var y = event.offsetY;
        // render
        // send the click to the backend
        var click = [this.index, x, y, isPositive];
        clicks.push(click);
        var lenandclick = [clicks.length, click];
        var ok = postData('addClick', 'click', lenandclick);
        if (ok) {
            this.renderDisplay();
            kSlider.max = (clicks.length - 1).toString();
        } else {
            console.log('click couldnt be added')
            console.log(ok)
            // remove last click from list of clicks
            clicks.pop()
        }
    }


    renderDisplay = async function() {
        // wait until the image is loaded
        while (this.imgCanvas.width < 400) {
            // wait for 100 ms
            await new Promise(r => setTimeout(r, 100));
            console.log('waiting for image to load')
        }

        // clear display canvas
        this.displayCtx.clearRect(0, 0, this.displayCanvas.width, this.displayCanvas.height);
        // resize display canvas to match imgCanvas
        this.displayCanvas.width = this.imgCanvas.width;
        this.displayCanvas.height = this.imgCanvas.height;
        // draw image from imgCanvas into displayCanvas
        this.displayCtx.drawImage(this.imgCanvas, 0, 0);
        // draw all clicks in displayCanvas (positive in green, negative in red) as circles
        for (var i = 0; i < clicks.length; i++) {
            if (clicks[i][0] == this.index) {
                if (clicks[i][3]) {
                    this.displayCtx.strokeStyle = 'green';
                } else {
                    this.displayCtx.strokeStyle = 'red';
                }
                this.displayCtx.beginPath();
                this.displayCtx.arc(clicks[i][1], clicks[i][2], 5, 0, 2 * Math.PI);
                this.displayCtx.stroke();
            }
        }
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
    console.log('created viewer' + viewer.id)
    console.log(container)

    // post the image to the backend
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${httpAddress}/newImg`, {
        method: 'POST',
        body: formData,
        }).catch(error => {
            viewersWs = new WebSocket(wsAddress + "/viewers");  // this websocket is used to receive images from the backend
            console.log('resetting websocket')
            console.log('error' + error);
            alert('Error uploading image');
        });
    const response = await res.json();
    // add viewer to list of viewers

    console.log('response' + response);
}
fileInput.addEventListener('change', handleFileSelect);

function postData (endpoint, key, value) {
    // send a post request with the new value
    var statusOk = true
    fetch(`${httpAddress}/${endpoint}`, {
        method: 'POST',
        body: JSON.stringify({[key]: value}),
        headers: {
            'Content-Type': 'application/json'
        }
        })
    .then(response => 
        response.json()
    )
    .then(data => console.log(data)).catch(error => {      
        console.log(error)
        statusOk = false
    });
    return statusOk
}

// function that handles the k slider
kSlider.onchange = function() {
    value = kSlider.value;
    postData('setK', 'k', value);
}

// threshSlider.onchange = function() {
//     value = threshSlider.value;
//     postData('setThresh', 'thresh', value);
// }


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


// get all the radio buttons with the name "featSpace"
var radios = document.querySelectorAll('input[name="featSpace"]');
// define the callback function
function handleChange(event) {
  // get the value of the selected radio button
  var value = event.target.value;
  postData('setFeatSpace', 'featSpace', value);
  console.log(value)
}
// loop through the radio buttons and add the event listener
for (var i = 0; i < radios.length; i++) {
  // add the "change" event listener to each radio button
  radios[i].addEventListener("change", handleChange);
}
