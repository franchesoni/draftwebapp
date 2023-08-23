// Description: main js file for the project
// code that handles input type="file" and shows the image

console.log("starting main.js");
const fileInput = document.getElementById('fileUpload');
const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');
const getRandomImgBtn = document.getElementById('getRandomImgBtn');
const ADDRESS = "http://localhost:8008";

// general data deader
// read the image and draw it on the canvas
const reader = new FileReader();
reader.onload = function(e) {
    img = new Image();
    img.onload = function() {
        canvas.width = img.width;
        canvas.height = img.height;
        ctx.drawImage(img, 0, 0);
        // imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    };
    img.src = reader.result;
};

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

    // post the image to the backend
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${ADDRESS}/setImg`, {
        method: 'POST',
        body: formData,
        })
    const response = await res.json();
    console.log(response);
    reader.readAsDataURL(file);
}

fileInput.addEventListener('change', handleFileSelect);
// now get image from /getImg endpoint and put it on the canvas
getRandomImgBtn.addEventListener('click', async () => {
    console.log("getRandomImgBtn clicked");
    const res = await fetch(`${ADDRESS}/getImg`);

    res.blob().then(blob => {
        reader.readAsDataURL(blob);
      });
})