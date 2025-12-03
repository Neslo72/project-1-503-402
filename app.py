import os, io
import json
from urllib.parse import quote_plus, urlencode
from functools import wraps
from flask import Flask, render_template, url_for, redirect, request, session, jsonify, send_file
from markupsafe import escape
import db

from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
from markupsafe import escape

# Auto tool for scraping recipes
# https://docs.recipe-scrapers.com/
# from recipe_scrapers import scrape_me

from recipeUtil import scrape_link, get_ingredient_nutrition

import random

load_dotenv(".env")
app = Flask(__name__)
app.secret_key = os.environ.get("APP_SECRET_KEY")
db.setup()


## OAuth ##


oauth = OAuth(app)
oauth.register(
    "auth0",
    client_id=os.environ.get("AUTH0_CLIENT_ID"),
    client_secret=os.environ.get("AUTH0_CLIENT_SECRET"),
    client_kwargs={
        "scope": "openid profile email",
    },
    server_metadata_url=f'https://{os.environ.get("AUTH0_DOMAIN")}/.well-known/openid-configuration'
)


@app.route("/login")
def login():
    return oauth.auth0.authorize_redirect(
        redirect_uri=url_for("callback", _external=True)
    )


# TODO change this function to store only the data we need
@app.route("/callback", methods=["GET", "POST"])
def callback():
    token = oauth.auth0.authorize_access_token()
    session["user"] = token

    # Extract user info
    userinfo = token.get('userinfo', {})
    oauth_id = userinfo.get('sub')
    nickname = userinfo.get('nickname', '')

    if oauth_id:
        # Extract provider from oauth_id (e.g., "auth0|123" -> "auth0")
        oauth_provider = oauth_id.split('|')[0] if '|' in oauth_id else 'auth0'

        # Check if user exists in database, if not create them
        existing_user = db.get_user_by_oauth(oauth_id, oauth_provider)

        if not existing_user:
            # Create new user with nickname as initial username
            userID = db.create_user(oauth_id, oauth_provider, nickname)
            print(f"New user created: {oauth_id}")
        else:
            userID = existing_user.get("user_id")
            print(f"Existing user logged in: {oauth_id}")

        # add userID to session info
        session["userID"] = userID

    return redirect("/")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(
        "https://" + os.environ.get("AUTH0_DOMAIN")
        + "/v2/logout?"
        + urlencode(
            {
                "returnTo": url_for("home", _external=True),
                "client_id": os.environ.get("AUTH0_CLIENT_ID"),
            },
            quote_via=quote_plus,
        )
    )


## Helper functions ##


# Get image data from formdata image
# Returns (image data, error message)
def parse_image_data(image):

    # Ensure image datatype
    if not hasattr(image, 'filename') or not hasattr(image, 'read'):
        return None, f"Passed argument is not a proper stream - {image}"

    # Enforce image extensions
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    file_ext = image.filename.rsplit('.', 1)[1].lower() if '.' in image.filename else ''
    if file_ext not in allowed_extensions:
        return None, f"Invalid file extension - {file_ext}"

    # Limit file size (e.g., 5MB)
    data = image.read()
    if len(data) > 5 * 1024 * 1024:
        return None, f"Image size too large (limit 5MB) - {len(data)}"
    
    return data, None


## App Links ##


@app.route("/")
def home():
    user = 'user' in session # change to session user
    recipes = db.get_recipes(limit=6)
    print([recipe.keys() for recipe in recipes])
    ratings = ["★ ★ ★ ★ ☆", "★ ★ ★ ★ ★"]
    recipe_items = {"trending": [], "top_rated": [], "recent": []}
    # need to add these keys cause the table doesn't contain them
    # checking if backend data and front end is the smae

    tag_names = db.get_tag_name()
    with db.get_db_cursor(commit=False) as cur:
        recipe_items = {
            "trending": db.get_recipes(limit=6, cur=cur),
            "top_rated": db.get_recipes(limit=6, minAvgRating=3, cur=cur),
            "recent": db.get_recipes(limit=6, recent=True, cur=cur)
        }
        print(len(recipe_items["trending"]))
        print(len(recipe_items["top_rated"]))
        print(len(recipe_items["recent"]))

        
    return render_template("main.html", user=user, recipes=recipe_items, tags=tag_names)

@app.route("/search", methods=["GET", "POST"])
def search():
    user = 'user' in session  
    tags = db.get_tag_name()
    explore_more = db.get_recipes(limit=8, random=True)
    if request.method == "GET":
        query = request.args.get("q", "").strip()
        print(query)
        results = db.get_recipes(titleTerms=[query], limit=5)
        print(results)
        return render_template("search.html", user=user, results=results, query=query, explore_recipes=explore_more)


    if request.method == "POST":
        tag_string = request.form.get("tags", "")
        selected_tags = [t.strip() for t in tag_string.split(",") if t.strip()]
        print("selected ",selected_tags)
        # Convert tag names to IDs using your dictionary
        selected_tag_ids = [db.tags[t] for t in selected_tags if t in db.tags]

        print("Converted tag IDs:", selected_tag_ids)
        results = db.get_recipes(tags=selected_tag_ids, limit=5)
        print(results)
        
        return render_template("search.html", user=user, results=results, selected_tag=tag_string, explore_recipes=explore_more)
        # recipe_q = request.form.get("query", "")
        # tag_string = request.form.get("tags", "")
        # selected_tags = [t.strip() for t in tag_string.split(",") if t.strip()]
        # print("selected ",selected_tags)
        # # Convert tag names to IDs using your dictionary
        # selected_tag_ids = [db.tags[t] for t in selected_tags if t in db.tags]

        # print("Converted tag IDs:", selected_tag_ids)
        # if recipe_q == "" and selected_tags == []:
        #     return render_template("search.html", user=user, tags=tags)
        
        # # if we are browsing based on category
        # query = recipe_q
        # if len(selected_tag_ids) > 0 and recipe_q == "":
        #     query = " ".join(selected_tags)
        
        # print("recipe query ", recipe_q)
        # results = db.get_recipes(titleTerms=[recipe_q], tags=selected_tag_ids, limit=5)
        # print(results)

        # return render_template("search_results.html", user=user, results=results, query=query)
    return render_template("/")
    
    

# TODO jinja template needs to be reworked
@app.route("/recipe/<int:id>")
# @app.route("/recipe")
def recipe(id=None):
    user = 'user' in session
    recipe_item = db.get_recipe(id)
    if recipe_item is None:
        return render_template("404.html", message=f"Recipe {id} not found", user=True), 404
    
    comments = db.get_comments(id)
    children_map = {}
    roots = []
    for c in comments:
        pid = c.get("parentid")
        if pid:
            children_map.setdefault(pid, []).append(c)
        else:
            roots.append(c)
    
    user_id = session.get("userID")
    user_rating = db.get_user_rating(id, user_id) if user_id else None
    
    is_saved = db.is_recipe_saved(id, user_id) if user_id else False
    
    return render_template("recipe.html", recipe=recipe_item, comments=comments, comment_roots=roots, comment_children=children_map, user_rating=user_rating, is_saved=is_saved,  user=user)


@app.route("/api/recipe/<int:recipeID>/comments", methods=["POST"])
def add_recipe_comment(recipeID):
    userID = session.get("userID")
    if not userID:
        return jsonify({"success": False, "message": "Login required"}), 401

    content = request.form.get("content") if request.form else None
    if content is None and request.is_json:
        content = (request.json or {}).get("content")

    parentID = None
    if request.is_json and (request.json or {}).get("parentID") is not None:
        parentID = (request.json or {}).get("parentID")
    elif request.form and request.form.get("parentID"):
        parentID = request.form.get("parentID")
    parentID = int(parentID) if parentID not in (None, "", "null") else None

    content = (content or "").strip()
    if not content:
        return jsonify({"success": False, "message": "Comment cannot be empty"}), 400
    if len(content) > 1023:
        return jsonify({"success": False, "message": "Comment too long (max 1023 chars)"}), 400

    if db.get_recipe(recipeID) is None:
        return jsonify({"success": False, "message": "Recipe not found"}), 404

    if parentID is not None:
        with db.get_db_cursor(commit=False) as cur:
            cur.execute("SELECT 1 FROM comments WHERE commentid = %s AND recipeid = %s", (parentID, recipeID))
            if cur.fetchone() is None:
                return jsonify({"success": False, "message": "Parent comment not found"}), 400

    safe_content = escape(content)
    saved = db.add_comment(recipeID, userID, safe_content, parentID=parentID)
    return jsonify({"success": True, "comment": saved}), 201


@app.post("/api/comment/<int:commentID>/edit")
def edit_comment_api(commentID):
    user_id = session.get("userID")
    if not user_id:
        return jsonify(success=False, message="Unauthorized"), 401

    payload = request.get_json(silent=True) or {}
    content = (payload.get("content") or "").strip()
    if not content:
        return jsonify(success=False, message="Content required"), 400

    updated = db.update_comment(commentID, user_id, content)
    if not updated:
        return jsonify(success=False, message="Not allowed or not found"), 403

    return jsonify(success=True, comment=updated)


@app.post("/api/comment/<int:commentID>/delete")
def delete_comment_api(commentID):
    user_id = session.get("userID")
    if not user_id:
        return jsonify(success=False, message="Unauthorized"), 401

    ok = db.delete_comment(commentID, user_id)
    if not ok:
        return jsonify(success=False, message="Not allowed or not found"), 403

    return jsonify(success=True)

@app.post("/api/recipe/<int:recipeID>/save")
def toggle_save(recipeID):
    user_id = session.get("userID")
    if not user_id:
        return jsonify(success=False, message="Unauthorized"), 401

    data = request.get_json(silent=True) or {}
    desired = data.get("saved")

    if desired is None:
        desired = not db.is_recipe_saved(recipeID, user_id)

    db.submit_interact_save(recipeID, user_id, saved=bool(desired))

    return jsonify(success=True, saved=bool(desired))



##  GET - Pull up the recipe edit form, populate with existing data
##  POST - Update recipe on the DB, add or update records
@app.route("/recipe/edit", methods=["GET", "POST"])
@app.route("/recipe/edit/<int:recipeID>", methods=["GET", "POST"])
def recipeEdit(recipeID=None, recipe={}):

    # Handle GET requests
    if request.method == "GET":
        if request.args.get("recipeID"):
            print(f"/recipe/edit/{request.args.get("recipeID")}")
            return redirect(f"/recipe/edit/{request.args.get("recipeID")}")
    
        if recipeID == None:

            # Check submitted autofill link
            link = request.args.get("recipe-link")
            linkType = request.args.get("link-type")
            if linkType == "CLEAR":
                return redirect("/recipe/edit")
            
            # Try auto filling the form
            elif link != None:
                recipe = scrape_link(link)
                if recipe == None:
                    recipe = {"linkstatus": "Unable to parse link"}
                return render_template("recipe-edit.html", recipe=recipe, user=True)
            
            else:
                return render_template("recipe-edit.html", recipe={}, user=True)
        
        # RecipeID exists, load data (pending ownership)
        else:
            recipe = db.get_recipe(recipeID)
            if (recipe is None) or (recipe.get("userid") != session.get("userID")):
                return redirect("/recipe/edit")
            return render_template("recipe-edit.html", recipe=recipe, edit=True, user=True)

    # Handle POST request
    elif request.method == "POST":

        # Confirm data submitted is json data
        if not request.content_type.startswith('multipart/form-data'):
            return {"message": "POST request requries content type multipart/form-data"}

        # Verify login status
        userID = session.get("userID")
        if userID == None:
            return {"message": "You must be logged in to post recipes!"}, 400

        # Check if image is OK before any DB stuff
        #   Overwrite recipe["imageFile"] if file exist
        #   Overwrite recipe["imageLink"] if url contains our path
        imageLink = request.form.get("imageLink")
        imageFile = request.files.get('imageFile')
        if imageFile != None:
            imageFile, err = parse_image_data(imageFile)
            if err != None:
                return {"message":err}, 400
            else:
                imageLink = None
        if imageLink == None or url_for("image_url") in imageLink:
            imageLink = None

        # Verify ownership
        ## TODO move verification to db.submit_recipe??  makes less db calls
        oldRecipe = db.get_recipe(recipeID)
        if (oldRecipe != None) and (oldRecipe.get("userid") != session.get("userID")):
            return {"message": "You do not have ownership of this reicpe!"}, 400

        # Can now submit recipe, so parse and post it
        recipe = request.form.to_dict(flat=True)
        recipe["tags"] = request.form.getlist("tags")
        recipe["steps"] = request.form.getlist("steps")
        recipe["ingredients"] = request.form.getlist("ingredients")
        recipe["draft"] = recipe.get("draft", False)
        recipe["userID"] = userID
        recipe["nutrients"] = json.loads(request.form.get("nutrients"))

        recipeID = db.submit_recipe(
            recipe, 
            recipeID=recipeID,
            imageFile=imageFile,
            imageLink=imageLink
        )

        if recipeID == None:
            print("rejected new recipe")
            return redirect(f"/recipe/edit/{recipeID}?status=FAILURE") 

        if recipe["draft"]:
            return redirect(f"/profile?drafts=True")
        return redirect(f"/recipe/{recipeID}")  # Hard redirect to /id


# Delete a recipe, need to have ownership of recipe
@app.post("/recipe/<int:recipeID>/delete")
def delete_recipe(recipeID):
    userID = session.get("userID")
    if not userID:
        return redirect("/login")

    recipe = db.get_recipe(recipeID)
    if recipe is None:
        return redirect(url_for("profile"))

    owner_id = recipe.get("userid") or recipe.get("userID")
    is_admin = bool(session.get("is_admin"))

    if not is_admin and (owner_id is None or int(owner_id) != int(userID)):
        return redirect(url_for("recipe", id=recipeID))

    ok = db.delete_recipe(recipeID=recipeID, userID=userID, is_admin=is_admin)
    return redirect(url_for("profile"))

@app.post("/api/recipe/<int:recipeID>/rate")
def rate_recipe(recipeID):
    userID = session.get("userID")
    if not userID:
        return jsonify({"success": False, "message": "Login required"}), 401

    if db.get_recipe(recipeID) is None:
        return jsonify({"success": False, "message": "Recipe not found"}), 404

    payload = request.get_json(silent=True) or {}
    try:
        rating = int(payload.get("rating", 0))
    except Exception:
        rating = 0

    if rating < 1 or rating > 5:
        return jsonify({"success": False, "message": "Rating must be 1-5"}), 400

    if db.has_user_rated(recipeID, userID):
        existing = db.get_user_rating(recipeID, userID)
        return jsonify({
            "success": False,
            "message": "You have already rated this recipe.",
            "existing_rating": existing
        }), 409

    db.submit_interact(recipeID, userID, rating=rating)

    fresh = db.get_recipe(recipeID) or {}
    avg = fresh.get("avg_rating") or 0
    count = fresh.get("ratings") or 0

    return jsonify({
        "success": True,
        "rating": rating,
        "avg_rating": float(avg),
        "ratings_count": int(count),
        "locked": True
    }), 200

@app.post("/api/recipe/<int:recipeID>/save")
def save_recipe(recipeID):
    if "userID" not in session:
        return jsonify(success=False, message="Unauthorized"), 401

    want_saved = bool(request.json.get("saved"))
    db.submit_interact_save(recipeID, session["userID"], saved=want_saved)
    return jsonify(success=True, saved=want_saved)

# Get nutritional matches from the USDA
# Works on singular ingredient string
@app.route("/api/nutrition", methods=["GET"])
def getNutrition():
    nutrients = get_ingredient_nutrition(request.args.get("ingredient"))
    if nutrients == None:
        return jsonify(success=False)
    return jsonify(success=True, data=nutrients)
    


## User Info ##



def get_authenticated_user():
    user = session.get('user')
    if not user:
        return None, None, None

    userinfo = user.get('userinfo', {})
    oauth_id = userinfo.get('sub')
    nickname = userinfo.get('nickname', '')  # Get nickname from Auth0

    if not oauth_id:
        return None, None, None

    # Extract provider from oauth_id (e.g., "auth0|123" -> "auth0")
    oauth_provider = oauth_id.split('|')[0] if '|' in oauth_id else 'auth0'

    return oauth_id, oauth_provider, nickname


@app.route("/api/save-profile", methods=['POST'])
def save_profile_data():
    try:
        # Authenticate user
        oauth_id, oauth_provider, nickname = get_authenticated_user()
        if not oauth_id:
            return jsonify({"success": False, "message": "User not logged in"}), 401

        # Sanitize user inputs to prevent XSS
        name = escape(request.form.get('name', '').strip())
        bio = escape(request.form.get('bio', '').strip())

        # Use nickname as default if name is empty
        if not name and nickname:
            name = escape(nickname.strip())

        # Validate input lengths
        if len(name) > 100:
            return jsonify({"success": False, "message": "Name too long"}), 400
        if len(bio) > 500:
            return jsonify({"success": False, "message": "Bio too long"}), 400

        # Handle image upload
        image = request.files.get('image')
        image_data = None
        if image != None:
            image_data, err = parse_image_data(request.files.get('image'))
            if err != None:
                return jsonify({"success": False, "message":err}), 400

        # Check if profile exists, if not insert, otherwise update
        existing_profile = db.get_profile_data(oauth_id, oauth_provider)

        if existing_profile:
            # Update existing profile
            db.update_profile(oauth_id, oauth_provider, name, bio, image_data)
        else:
            # Insert new profile
            db.insert_profile_image(oauth_id, oauth_provider, name, bio, image_data)

        return jsonify({"success": True, "message": "Profile saved!"}), 200

    except Exception as e:
        print(f"Error saving profile: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": "Internal server error"}), 500


@app.route("/api/get-profile", methods=['GET'])
def get_profile_data():
    """Retrieve user profile data."""
    try:
        # Authenticate user
        oauth_id, oauth_provider, nickname = get_authenticated_user()
        if not oauth_id:
            return jsonify({"success": False, "message": "User not logged in"}), 401

        profile = db.get_profile_data(oauth_id, oauth_provider)

        # If no profile exists yet, return nickname as default name
        if not profile:
            profile = {
                'name': nickname,
                'bio': '',
                'image': None
            }
        elif not profile.get('name') and nickname:
            # If profile exists but name is empty, use nickname
            profile['name'] = nickname

        return jsonify({
            "success": True,
            "profile": profile
        }), 200

    except Exception as e:
        print(f"Error getting profile: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": "Internal server error"}), 500


## Allow image hosting on our site
##  returns a url of the image
@app.route("/api/image", methods=["GET"])
def image_url(imageID=None, recipeID=None, userID=None):

    # Use request args if a GET requst made
    imageID = imageID or request.args.get("imageID")
    recipeID = recipeID or request.args.get("recipeID")
    userID = userID or request.args.get("userID")

    image = db.get_image(imageID, recipeID, userID)
    if image == None:
        return {"success":False, "message":"Unable to find requested image"}, 400

    if not isinstance(image, bytes):
        return redirect(image)
    else:
        return send_file(
            io.BytesIO(image),
            mimetype='image/jpeg',
            as_attachment=False,
            download_name='profile.jpg'
        )

@app.route("/api/profile-image", methods=['GET'])
def get_profile_image():
    return redirect(url_for("image_url", userID=session.get("userID")))


@app.route("/profile")
def profile():
    
    user = 'user' in session

    if not user:
        return redirect('/login')
    
    userID = session.get('userID')
    # Reuse cursor with a few calls
    with db.get_db_cursor(commit=False) as cur:

        saved_recipes = db.get_user_interactions(userID, saved=True, cur=cur)
        user_posts = db.get_user_posts(userID, cur=cur)
        user_drafts = db.get_user_drafts(userID=userID, cur=cur)

        return render_template(
            "profile.html",
            user=True,
            session=session.get('user'),
            user_posts=user_posts,
            saved_recipes=saved_recipes,
            user_drafts=user_drafts
        )


## Execute Server ##


# python sever.py
if __name__ == '__main__':
    app.run(debug=True, port=5000)
