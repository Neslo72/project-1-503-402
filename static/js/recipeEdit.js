const ingZone = document.querySelector("#ingredient-zone");
const stepZone = document.querySelector("#step-zone");


// Update nutrients display
function updateNutrients(nutrients)
{
    const labels = ["", " g", " g", " g", " g", " g", " mg", 
        " mg", " mg", " mg", " µg", " mg", " mg", " g", " g"
    ];

    const nutLabel = document.querySelector("#nutrition-label");
    for(let i = 0; i < labels.length; i++) {
        const label = nutLabel.querySelector(`#nut-${i}`);
        let value = parseFloat(nutrients[i])
        if (isNaN(value))
            value = "--"
        else if(label)
            label.innerHTML = value.toFixed(2) + labels[i];
    }

    let servings = parseInt(document.querySelector("#servings").value);
    if(isNaN(servings))
        servings = "--"
    nutLabel.querySelector("#nut-servings").innerHTML = `Total Servings: ${servings}`
}

// Calculate nutritional estimate from input elements
function calcEstimate() {
    let total = Array(15).fill(0);
    const items = ingZone.querySelectorAll("li");
    for(const item of items)
    {
        let grams = item.querySelector("input[type=number]");
        if(grams)
            grams = parseFloat(grams.value)

        // let nutrients = `[${item.querySelector("select").value}]`;
        // if(nutrients === null || nutrients === "")
        //     continue
        // nutrients = JSON.parse(nutrients)

        let nutrients = item.querySelector("select");
        if(!nutrients)
            continue
        nutrients = JSON.parse(`[${nutrients.value}]`)

        for(let i = 0; i < nutrients.length; i++)
            total[i] += nutrients[i] * grams;
    }

    let servings = parseInt(document.querySelector("#servings").value);
    if(isNaN(servings))
        servings = 1;

    for (let i = 0; i < total.length; i++)
        total[i] = (total[i]  / servings).toFixed(2);
    return total
}


// Estimate list item ingredient
// Returns 1 for initial page load (load nutritional label)
async function estimateIngredient(item, text) {

    // Setup USDA ingredient select
    const params = new URLSearchParams({"ingredient": text})
    return fetch(`/api/nutrition?${params.toString()}`)
    .then(raw => raw.json())
    .then(res => {

        const span = item.querySelector("span");
        if(!res || !res.success) {
            span.innerHTML = "Unable to find suitable data"
            return 1;
        }
        span.innerHTML = "USDA Nutritional Match: "
        const grams = span.appendChild(document.createElement("input"));
        grams.type = "number";
        grams.step = "0.01"
        grams.className = "USDA_grams"
        grams.value = res.data[0].amount;
        span.insertAdjacentText("beforeend", " grams of ");

        const select = span.appendChild(document.createElement("select"));
        select.className = "USDA_base"
        const noOpt = select.appendChild(document.createElement("option"));
        noOpt.value = "";
        noOpt.innerHTML = "None";

        for(const nutrient of res.data) {
            const opt = select.appendChild(document.createElement("option"));
            opt.value = `${nutrient.nutrition}`
            opt.innerHTML = nutrient.name
        }
        select.options[1].selected = true
        return 1;
    })
    .catch(_ => {
        const span = item.querySelector("span");
        span.innerHTML = "Unable to find suitable data"
        return 1;
    });
}


// Measurement / ingredient form management
document.querySelector("#ing-add").addEventListener("click", () => 
{
    const ingInput = document.querySelector("#ing-input");
    if(ingInput.value === "")
        return;
    const value = ingInput.value;

    const item = ingZone.appendChild(document.createElement("li"));
    item.className = "step-list";

    const text = item.appendChild(document.createElement("input"));
    text.className = "pure-input-2-3";
    text.type = "text"
    text.value = value;
    text.readOnly = true;

    const remove = item.appendChild(document.createElement("button"));
    remove.type = "button";
    remove.className = "pure-button-secondary";
    remove.innerHTML = "Remove";

    const msg = item.appendChild(document.createElement("span"));
    msg.className = "pure-form-message";
    msg.innerHTML = "Calculating USDA ingredient match..."

    ingInput.value = "";
    estimateIngredient(item, value)
    .then(() => {
        updateNutrients(calcEstimate());
    });
});


// Update label on servings change
document.querySelector("#servings").addEventListener("change", (event) => {
    if(isNaN(event.target.value))
        event.target.value = 1;
    updateNutrients(calcEstimate());
});


// Nutrition management
ingZone.addEventListener("input", (event) => {
    updateNutrients(calcEstimate());
})

// Remove ingredients
ingZone.addEventListener("click", (event) => {
    if(event.target.innerHTML === "Remove") {
        event.target.closest("li").remove()
        updateNutrients(calcEstimate());
        return;
    }
})


// Step form management
// TODO need to flesh out like ingredient management
// CAN ALSO be very polished
document.querySelector("#step-add").addEventListener("click", () => {

    const stepEdit = document.querySelector("#step-edit");
    if(stepEdit.value === "")
        return;

    const step = document.createElement("li");
    const tbox = document.createElement("textarea");

    tbox.innerHTML = stepEdit.value;
    step.className = "step-list"
    step.appendChild(tbox);
    
    const remove = step.appendChild(document.createElement("button"));
    remove.type = "button";
    remove.className = "pure-button-secondary";
    remove.innerHTML = "Remove";
    remove.addEventListener("click", () => {
        step.remove();
    });

    stepEdit.value = "";
    stepZone.appendChild(step);
});

// Clear step edit box
document.querySelector("#step-clear").addEventListener("click", () => {
    document.querySelector("#step-edit").value = "";
});

// Allow edits to previous steps
stepZone.addEventListener("click", (event) => 
{
    const tbox = event.target;
    if(tbox.tagName.toLowerCase() !== "textarea")
        return;
});


// Tag selection
const tagContainer= document.querySelector("#tag-container")
tagContainer.addEventListener("click", (event) => 
{
    if(event.target.id === "tag-container")
        return;

    if(event.target.classList.contains("tag-select"))
        event.target.classList.remove("tag-select");
    else
        event.target.classList.add("tag-select");
});


// Image upload
const imageUpload = document.querySelector("#imageFile")
let imageContainer = document.querySelector("#img-container")
imageUpload.addEventListener("change", (event) => {

    const file = event.target.files[0]
    if(!file)
        return;

    const fReader = new FileReader();
    fReader.onload = (event) => {
        imageContainer.src = event.target.result;
        imageContainer.style.display = "";
    } 
    fReader.readAsDataURL(file)
})


// TODO rigorous form checking needed on server
// Hijack the form submission and add extras not in the form
const form = document.querySelector("#recipe-form");
form.addEventListener("submit", (event) => {

    event.preventDefault();

    // standard form data
    const formData = new FormData(form);

    // link (if autofilled)
    const linkBox = document.querySelector("#recipe-link");
    if(linkBox && linkBox.readOnly)
        formData.set("link", linkBox.value);
    else
        formData.set("link", linkBox.value);

    // tags
    const tagList = tagContainer.querySelectorAll(".tag-select");
    for(const tagItem of tagList)
        formData.append("tags", tagItem.id)

    // ingredients / nutrition
    let nutrients = [{total: calcEstimate()}]
    const ingredients = ingZone.querySelectorAll("li");
    for(let item of ingredients) {

        const ing = item.querySelector("input[type=text]");
        formData.append("ingredients", ing.value);

        let grams = item.querySelector("input[type=number]");
        let name = item.querySelector("select")
        if(grams && name) {
            grams = parseFloat(grams);
            name = name.selectedOptions[0];
            nutrients.push({
                name: name.innerHTML.trim(),
                amount: grams,
                nutrients: name.value
            })
        }
        else {
            nutrients.push({
                name: "No match",
                amount: 0,
                nutrients: `${Array(15).fill(0)}`
            })
        }

    }
    formData.set("nutrients", JSON.stringify(nutrients))

    // Steps
    const steps = stepZone.querySelectorAll("textarea");
    for(let step of steps)
        formData.append("steps", step.innerHTML);

    // image
    if(imageUpload.files.length > 0)
        formData.set("imageFile", imageUpload.files[0]);
    else
        formData.set("imageLink", imageContainer.src);

    // Post or draft
    if(event.submitter.id === "draft-button")
        formData.set("draft", true)

    // POST to server
    fetch(window.location.pathname, {
        method: 'POST',
        body: formData
    })
    .then(resp => {
        if (resp.redirected)
            window.location.href = resp.url  // redirect
        return
    })
    .catch(err => {
        console.log(`FORM SUBMISSION - ${err}`)
    })
});


// TODO clear all form elements, including ingrident list step list etc..
document.querySelector("#clear-all").addEventListener("click", () => {
    window.location.href = "/"
});

// Load nutritional info on document load
document.addEventListener("DOMContentLoaded", () => {
    let results = []
    const items = ingZone.querySelectorAll("li");
    for(let item of items) {
        const text = item.querySelector("input[type=text]");
        const grams = item.querySelector("input[type=number]");
        if(grams == null || !grams.readOnly)
            results.push(estimateIngredient(item, text.value));
    }

    // Once all promises resolved, calculate nutritional label
    Promise.all(results).then(() => {
        updateNutrients(calcEstimate())
    });
});


// Delete button
const deleteButton = document.querySelector("#delete-button");
if(deleteButton) {
    deleteButton.addEventListener("click", (event) => {
        fetch(`/recipe/${event.target.value}/delete`, {
            method: "POST"
        })
        .then(() => {
            window.location.href = "/"
        })
    })   
}