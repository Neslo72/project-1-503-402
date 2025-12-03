import os
import csv
import requests
import concurrent.futures
from pint import UnitRegistry

# Auto tool for scraping recipes
# https://docs.recipe-scrapers.com/
from recipe_scrapers import scrape_me

# Auto tool for parsing ingredients
# https://github.com/strangetom/ingredient-parser
from ingredient_parser import parse_ingredient, parse_multiple_ingredients

## FOUNDATION FOODS DATASET
## https://fdc.nal.usda.gov/api-guide


# Load table of estimated densities (g/ml)
def loadDensities(csv_path):
    densities = {}
    with open(csv_path, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cat = row['category']
            min = float(row['min']) if row['min'] else None
            max = float(row['max']) if row['max'] else None

            # Set null values
            if min != None and max != None:
                avg = (min + max) / 2
            elif min == None and max == None:
                avg, min, max = 1, 1, 1
            elif min == None:
                avg, min = max, max
            elif max == None:
                avg, max = min, min

            densities[cat] = (avg, min, max)
        return densities

# Get average by DENSITIES[key][0]
DENSITIES = loadDensities("densities.csv")

# Define a unit conversion registry
# Add some custom approximations
UREG = UnitRegistry()
UREG.define("can = 10.5 * oz = cans")
UREG.define("stalk = 7 * oz = stalks")
UREG.define("stick = 8 * oz = sticks")

# USDA api key
USDA_API_KEY = os.getenv('USDA_API_KEY')

# Indicies aligned, API keys for the below nutrients
NUTRIENT_KEYS = ['203', '204', '205', '269', '291', '301', '303', '306', '307', '320', '401', '601', '605', '606']
NUTRIENTS = ['Protein (g)', 'Total Fat (g)', 'Carbohydrates (g)', 'Sugars (g)', 'Fiber (g)', 'Calcium (mg)', 'Iron (mg)', 'Potassium (mg)', 'Sodium (mg)', 'Vitamin A (µg)', 'Vitamin C (mg)', 'Cholesterol (mg)', 'Trans Fat (g)', 'Saturated Fat (g)']
    

# Fetch USDA data by fdc_id
def fetch_usda_data(foods=[]):
    url = "https://api.nal.usda.gov/fdc/v1/foods"
    res = requests.get(url, params= {
        "fdcIds":       ",".join(foods),
        "nutrients":    ",".join(NUTRIENT_KEYS.keys()),
        "api_key":      USDA_API_KEY
    })
    # res.raise_for_status()
    return res.json()


# Search USDA data by name
def search_usda_data(food, pageSize=10):
    url = "https://api.nal.usda.gov/fdc/v1/foods/search"
    res = requests.get(url, params= {
        "query":        food,
        "api_key":      USDA_API_KEY,
        "pageSize":     pageSize
    })
    # res.raise_for_status()
    return res.json()


# Convert values from parser to gram estimates
def convert_grams(amount, category=""):

    if amount == None:
        return None

    # to Mass conversion (get grams)
    # We are approximating, skip ingredients with no compareable units
    unitName = f"{amount.unit}".lower()
    if unitName not in UREG:
        # TODO could look into RTCC in fetch_usda_data (leave approx for now)
        return None
    
    # Calculate approximate mass for USDA data
    if UREG(unitName).check("[mass]"):
        grams = (float(amount.quantity) * UREG(unitName)).to("gram").magnitude
    elif UREG(unitName).check("[volume]"):
        density = DENSITIES.get(category)
        density = (density[0] if density else 1) * UREG("gram / milliliter")
        volume = float(amount.quantity) * UREG(unitName)
        grams = (volume * density).to("gram").magnitude
    else:
        grams = 0
    
    return round(grams, 2)


# Extract nutrients from USDA data
# Store as per 1 gram (USDA data is stored as 100 grams)
def extract_nutrients(food, grams):
    kcal = 0
    nutrients = [0 for i in range(len(NUTRIENT_KEYS) + 1)]
    for item in food.get("foodNutrients", []):
        key = item["nutrientNumber"]
        value = round(item["value"] / 100, 2)
        match key:
            case "203":     # Protein
                kcal += value * 4
            case "204":     # Fat
                kcal += value * 9
            case "205":     # Carbs
                kcal += value * 4
        if key in NUTRIENT_KEYS:
            nutrients[NUTRIENT_KEYS.index(key) + 1] = value     
    nutrients[0] = round(kcal, 2)
    return nutrients


# Get nutrient approximation for 1 ingredient
# Returns (max 5) options
def get_nutrients(ingredient):
    
    if ingredient.name == None:
        return
    rawName = ingredient.name[0].text
    nutrients = []

    # Convert units from the recipe parser
    if ingredient.amount == None or len(ingredient.amount) <= 0:
        amount = None
    else:
        amount = ingredient.amount[0]
        if amount.unit == None or amount.unit == "" or amount.quantity == "":
            amount = None

    # Loop over options
    for food in search_usda_data(rawName).get("foods", []):

        name = food.get("description", "").lower()

        # Skip if similarly named product already found
        skip = False
        for nut in nutrients:
            if name == nut["name"]:
                skip = True
                break
        if skip:
            continue

        # Approximate the # of grams
        grams = convert_grams(amount, food.get("foodCategory"))
        if grams == None:
            grams = 0

        # Scale USDA data to 1gram             
        nutrients.append({ 
            "name" : name, 
            "amount": grams,
            "nutrition": extract_nutrients(food, grams)
        })

    if len(nutrients) > 0:
        return { ingredient.sentence: nutrients}
    return None


# Run multiple threaded searches, sum nutritional values
# Returns (max 5) options per ingredient
def get_multiple_nutrients(ingredients):
    nutrients = {}
    with concurrent.futures.ThreadPoolExecutor(10) as executor:
        futures = {executor.submit(get_nutrients, ing): ing for ing in ingredients}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res != None:
                nutrients = nutrients | res
        
        return nutrients


# Get nutrition for 1 ingredient
def get_ingredient_nutrition(ingredient):
    parsed = parse_ingredient(ingredient)
    if parsed == None:
        return None
    
    nutrients = get_nutrients(parsed)
    if nutrients == None:
        return {"ingredient": ingredient, "nutrients": [0] * 15}
    return nutrients[parsed.sentence]


# The one to call
# Uses previous functions to compile nutritional data
def get_recipe_nutrition(recipe):

    ingredients = recipe["ingredients"]
    unsorted_nutrients = get_multiple_nutrients(
        parse_multiple_ingredients(sentences=ingredients)
    )

    nutrients = [None for i in range(len(ingredients))]
    for ing in unsorted_nutrients.keys():
        if ing in ingredients:
            nutrients[ingredients.index(ing)] = unsorted_nutrients[ing]
        else:
            print(f"NOT FOUND? {ing}")

    print(nutrients)
    return nutrients


# Scrape recipe from link
def scrape_link(link):
    try:
        scraper = scrape_me(link)
        raw = scraper.to_json()
        recipe = {
            "link": raw.get("canonical_url"),
            "title": raw.get("title"),
            "brief": raw.get("description"),
            "cooktime": raw.get("total_time"),
            "servings": raw.get("yields", "").split(" ")[0],
            "steps": raw.get("instructions_list"),
            "kcal": raw.get("nutrients", {}).get("calories", "").split(" ")[0],
            "image_url": raw.get("image")   # this is a link (good)
        }

        # Parse mixed fractions
        ingredients = []
        for ing in raw.get("ingredients"):
            tokens = ing.split(" ")

            value = 0.0
            text = []
            for i in range(len(tokens)):
                try:
                    frac = tokens[i].split("/")
                    if len(frac) > 1:
                        value += float(frac[0]) / float(frac[1])
                    else:
                        value += float(frac[0])
                except:
                    value = round(value, 2)
                    text = [str(value)] + tokens[i:]
                    break
            ingredients.append(" ".join(text))
            
        return recipe | {"ingredients": ingredients}
    
    except Exception as e:
        print(f"Error parsing recipe link - {link}")
        print(e)
        return None


# print(get_recipe_nutrition(scrape_link("https://www.allrecipes.com/recipe/8309691/italian-sunday-sauce/")))
