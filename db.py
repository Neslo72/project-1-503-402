## Taken and modified from Professor Kluver's 9/25 in class demo and repo
## Repo: https://github.com/csci5117f25/session-06-in-class-render-test-kluver/tree/main
## Original File: https://github.com/csci5117f25/session-06-in-class-render-test-kluver/blob/main/db.py

""" database access
docs:
* http://initd.org/psycopg/docs/
* http://initd.org/psycopg/docs/pool.html
* http://initd.org/psycopg/docs/extras.html#dictionary-like-cursor
"""

from contextlib import contextmanager
import logging
import os
from typing import override

from flask import current_app, g

# import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import DictCursor, execute_values, Json

pool = None

# Dictionary of tags to tagIDs on the database
#   (Small enough to hardcode)
tags = {
    "air-fryer": 1,
    "appetizer": 2,
    "baking": 3,
    "beef": 4,
    "bread": 5,
    "breakfast": 6,
    "brunch": 7,
    "budget": 8,
    "chicken": 9,
    "classic": 10,
    "comfort": 11,
    "dairy-free": 12,
    "dessert": 13,
    "dinner": 14,
    "easy": 15,
    "family-friendly": 16,
    "fresh": 17,
    "gluten-free": 18,
    "grilling": 19,
    "healthy": 20,
    "high-protein": 21,
    "holiday": 22,
    "instant-pot": 23,
    "kid-friendly": 24,
    "lunch": 25,
    "low-carb": 26,
    "main-course": 27,
    "meal-prep": 28,
    "modern": 29,
    "one-pot": 30,
    "pasta": 31,
    "pork": 32,
    "quick": 33,
    "rice": 34,
    "salad": 35,
    "seafood": 36,
    "side-dish": 37,
    "slow-cooker": 38,
    "snack": 39,
    "soup": 40,
    "spicy": 41,
    "summer": 42,
    "vegan": 43,
    "vegetarian": 44,
    "winter": 45
}


## General database


def setup():
    global pool
    DATABASE_URL = os.environ["DATABASE_URL"]
    # current_app.logger.info(f"creating db connection pool")
    pool = ThreadedConnectionPool(1, 100, dsn=DATABASE_URL, sslmode="require")


@contextmanager
def get_db_connection():
    try:
        connection = pool.getconn()
        yield connection
    finally:
        pool.putconn(connection)


# Pass cur to allow the same cursor to be used
## NOTE if a commit is required, first cur init in chain must be True
@contextmanager
def get_db_cursor(commit=False, cur=None):
    if cur != None:
        yield cur
    else:
        with get_db_connection() as connection:
            cursor = connection.cursor(cursor_factory=DictCursor)
            try:
                yield cursor
                if commit:
                    connection.commit()
            finally:
                cursor.close()


## User management ##


def get_user_by_oauth(oauth_id, oauth_provider, cur=None):
    """Check if user exists in database."""
    with get_db_cursor(commit=False, cur=cur) as cur:
        cur.execute(
            "SELECT UserID, username, bio FROM Users WHERE OauthID = %s AND OauthProvider = %s",
            (oauth_id, oauth_provider)
        )
        result = cur.fetchone()
        if result:
            return {
                'user_id': result[0],
                'username': result[1],
                'bio': result[2]
            }
        return None


def create_user(oauth_id, oauth_provider, username, cur=None):
    """Create a new user on first login."""
    with get_db_cursor(commit=True, cur=cur) as cur:
        # Use nickname as initial username, with empty bio
        cur.execute(
            "INSERT INTO Users (OauthID, OauthProvider, username, bio, adminFlag) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING UserID",
            (oauth_id, oauth_provider, username, '', False)
        )
        user_id = cur.fetchone()[0]
        print(f"Created user with ID: {user_id}")
        return user_id


## Recipe dealings ##


# Submit data to postgres
## TODO deal with images and ingredients
def submit_recipe(recipe, recipeID=None, imageFile=None, imageLink=None, cur=None):

    with get_db_cursor(commit=True, cur=cur) as cur:

        # filter empty datapoints to None
        for key, value in recipe.items():
            recipe[key] = value if value != "" else None

        # Recipe dealings
        if(recipeID != None):
            query = """
            UPDATE recipes SET
                draft = %s, servings = %s, cooktime = %s,
                kcal = %s, title = %s, brief = %s, comment = %s, 
                steps = %s, ingredients = %s, nutrients = %s, lastedit = NOW()
            WHERE recipeid = %s
            RETURNING recipeID
            """
            queryData = (
                recipe.get("draft"), recipe.get("servings"), recipe.get("cooktime"),
                recipe.get("kcal"), recipe.get("title"), recipe.get("brief"), recipe.get("comment"), 
                Json(recipe.get("steps")), Json(recipe.get("ingredients")), Json(recipe.get("nutrients")),
                recipeID
            )

        else:
            query = """ 
            INSERT INTO recipes (
                userID, draft, servings, cooktime, kcal, title, brief, comment, link, steps, ingredients, nutrients, lastEdit
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
            )
            RETURNING recipeID
            """
            queryData = (
                recipe.get("userID"), recipe.get("draft"), recipe.get("servings"), recipe.get("cooktime"),
                recipe.get("kcal"), recipe.get("title"), recipe.get("brief"), recipe.get("comment"), 
                recipe.get("link"), Json(recipe.get("steps")), Json(recipe.get("ingredients")), Json(recipe.get("nutrients"))
            )

        # Update / add recipe data
        cur.execute(query, queryData)
        recipeID = cur.fetchone()[0]

        # Tag dealings
        # add / remove tags
        cur.execute("SELECT tagID FROM tagMatch WHERE recipeID = %s", (recipeID,))
        recipeTags = set([col[0] for col in cur.fetchall()])
        newTags = set(filter(lambda x: x!= None, [tags.get(tag) for tag in recipe.get("tags")]))        
        toRemove = list(recipeTags - newTags)
        cur.execute("DELETE FROM tagMatch WHERE recipeID = %s AND tagid = ANY(%s)", (recipeID, toRemove))
        
        toAdd = list(newTags - recipeTags)
        toAdd = [(recipeID, tagid) for tagid in toAdd]
        execute_values(cur, "INSERT INTO tagMatch (recipeID, tagID) VALUES %s", toAdd)

        # Submit an image
        submit_image(
            content=imageFile,
            title=f"Recipe {recipeID} image",
            link=imageLink,
            recipeID=recipeID, 
            userID=recipe.get("userID"), 
            cur=cur
        )

        ## TODO deal with nutrition
        # Stored in weird format
        # string {amount-[asdf, asdf, asdf]} nutrients index according to 
        # NUTRIENTS = ['Protein (g)', 'Total Fat (g)', 'Carbohydrates (g)', 'Sugars (g)', 'Fiber (g)', 'Calcium (mg)', 'Iron (mg)', 'Potassium (mg)', 'Sodium (mg)', 'Vitamin A (µg)', 'Vitamin C (mg)', 'Cholesterol (mg)', 'Trans Fat (g)', 'Saturated Fat (g)']

        # Return recipeID
        return recipeID


## THE ALMIGHTY get recipes query
## has an input for practically any option in filtering
def get_recipes(recipeIDs=[], userIDs=[], tags=[], titleTerms=[], 
                minAvgRating=None, minRatings=None, isDraft=False,
                limit=1, random=True, recent=False, cur=None
    ):

    with get_db_cursor(commit=False, cur=cur) as cur:
        
        query = "SELECT * FROM recipes r"
        queryData = []
        andFlag = False

        # Helper to add AND or WHERE
        def andWhere(toAdd, addAnd):
            if addAnd:
                return " AND" + toAdd
            else:
                return " WHERE" + toAdd

        # Prep tag filtering
        tagFilter = False
        if len(tags) > 0:
            tagFilter = True
            queryData.append(tags)

        # Start base query with filter
        query = f"""
            WITH ratings AS (
                SELECT recipeid, 
                    AVG(rating) AS avg_rating,
                    COUNT(rating) AS ratings, 
                    SUM(saved::int) AS saves
                FROM interactions GROUP BY recipeid
            ),
            tags AS (
                {"""
                WITH tagMatches AS (
                    SELECT DISTINCT tm.recipeid
                    FROM tagMatch tm
                    WHERE tm.tagid = ANY(%s)
                )
                """ if tagFilter else ""
                }
                SELECT tm.recipeid, array_agg(DISTINCT t.name) AS tags
                FROM tagMatch tm
                {"JOIN tagMatches tms ON tms.recipeid = tm.recipeid" if tagFilter else ""}
                JOIN tags t ON tm.tagid = t.tagid
                GROUP BY tm.recipeid  
            )
            SELECT r.*, t.tags, u.username AS author, avg_rating, ratings, saves
            FROM recipes r 
            {"LEFT" if not tagFilter else ""} JOIN tags t ON t.recipeid = r.recipeid
            LEFT JOIN ratings rr ON rr.recipeid = r.recipeid
            JOIN users u ON u.userid = r.userid
        """

        # Build a filter for each input
        if len(recipeIDs) > 0:
            query += andWhere(" r.recipeID = ANY(%s)", andFlag)
            queryData.append(recipeIDs)
            andFlag = True

        if isDraft != None:
            query += andWhere(" r.draft = %s", andFlag)
            queryData.append(isDraft)
            andFlag = True

        if len(userIDs) > 0:
            query += andWhere(" r.userID = ANY(%s)", andFlag)
            queryData.append(userIDs)
            andFlag = True

        if len(titleTerms) > 0:
            query += andWhere(" r.title ILIKE ANY(%s)", andFlag)
            queryData.append([f"%{item}%" for item in titleTerms])
            andFlag = True

        if minAvgRating != None:
            query += andWhere(" avg_rating >= %s", andFlag)
            queryData.append(minAvgRating)
            andFlag = True

        if minRatings != None:
           query += andWhere(" ratings > %s", andFlag)
           queryData.append(minRatings) 

        if random:
            query += " ORDER BY RANDOM()"
        elif recent:
            query += " ORDER BY r.lastedit"
        query += " LIMIT %s"
        queryData.append(limit)

        # Execute and return
        # print(query % tuple(queryData))
        cur.execute(query, tuple(queryData))
        res = cur.fetchall()

        return [ 
            dict(row) | {"image_url":f"/api/image?recipeID={row.get("recipeid", "")}"} for row in res 
        ]

    
# Wrapper for singular recipe
def get_recipe(recipeID, cur=None):
    res = get_recipes(recipeIDs=[recipeID], random=False, isDraft=None, limit=1, cur=cur)
    if len(res) > 0:
        return res[0]
    return None

# Wrapper for user drafts
def get_user_drafts(userID, cur=None):
    return get_recipes(userIDs=[userID], random=False, isDraft=True, limit=99, cur=cur)

# wrapper for user posts
def get_user_posts(userID, cur=None):
    return get_recipes(userIDs=[userID], random=False, limit=99, cur=cur)



# Delete a recipe with recipeID
def delete_recipe(recipeID, userID=None, is_admin=False, cur=None):

    with get_db_cursor(commit=True, cur=cur) as cur:
        cur.execute("SELECT userID FROM recipes WHERE recipeID = %s", (recipeID,))
        row = cur.fetchone()
        if not row:
            return False

        owner_id = row[0]
        if not is_admin and (userID is None or int(owner_id) != int(userID)):
            return False

        cur.execute("DELETE FROM comments WHERE recipeID = %s", (recipeID,))
        cur.execute("DELETE FROM interactions WHERE recipeID = %s", (recipeID,))
        cur.execute("DELETE FROM tagmatch WHERE recipeID = %s", (recipeID,))
        cur.execute("DELETE FROM images WHERE recipeID = %s", (recipeID,))

        cur.execute("DELETE FROM recipes WHERE recipeID = %s", (recipeID,))
        return True

    

### User Interactions ####


# Allow a user to interact with a recipe
# Not mean to be called, use wrapper functions (_save, _rating)
def _submit_interact(recipeID, userID, rating=None, saved=None, cur=None):
    with get_db_cursor(commit=True, cur=cur) as cur:

        queryData = [recipeID, userID]

        # Check if either field should be updated
        doRating = False
        if not (rating != None and rating == -1):
            doRating = True 
            queryData.append(rating)

        doSave = False
        if saved != None:
            doSave = True
            queryData.append(saved)

        # No interaction to report
        if not (doRating or doSave):
            return

        query = f"""
        INSERT INTO Interactions (
            recipeID, userID, 
            {"rating" if doRating else ""} 
            {", " if doRating and doSave else ""}
            {"saved" if doSave else ""}
        )
        VALUES (
            %s, %s,
            {"%s" if doRating else ""}
            {", " if doRating and doSave else ""}
            {"%s" if doSave else ""}
        )
        ON CONFLICT(recipeID, userID)
        DO UPDATE SET
            {"rating = EXCLUDED.rating" if doRating else ""}
            {", " if doRating and doSave else ""}
            {"saved = EXCLUDED.saved" if doSave else ""}
        """
        cur.execute(query, tuple(queryData))


# Allow recipe saves
# Ratings can be none, so make sure submit_interact does not overwrite rating (rating=-1)
def submit_interact_save(recipeID, userID, saved=False, cur=None):
    return _submit_interact(recipeID, userID, saved=saved, rating=-1, cur=cur)

# Allow recipe rates
def submit_interact_rating(recipeID, userID, rating=None, cur=None):
    return _submit_interact(recipeID, userID, rating=rating, cur=cur)


# Get user interactions
# rating is an array of ratings (filter which ratings to see)
# saved is a boolean filter
def get_user_interactions(userID, rating=[], saved=None, cur=None):
    with get_db_cursor(commit=False, cur=cur) as cur:
    
        queryData = [userID]

        doSave = False
        if saved != None:
            doSave = True
            queryData.append(saved)
        
        doRating = False
        if len(rating) > 0:
            doRating = True
            queryData.append(rating)

        query = f"""
        SELECT recipeid FROM interactions
        WHERE userid = %s
        {"AND saved = %s " if doSave else ""}
        {"AND rating = ANY(%s)" if doRating else ""}
        """
        cur.execute(query, tuple(queryData))

        res = cur.fetchall()
        recipeIDs = [row[0] for row in res]
        if len(recipeIDs) > 0:
            return get_recipes(recipeIDs=recipeIDs, random=False, limit=len(recipeIDs), cur=cur)
        return None


### User Profile ###


def insert_profile_image(oauth_id, oauth_provider, username, bio, image_data, cur=None):
    with get_db_cursor(commit=True, cur=cur) as cur:
        # Fetch existing user
        cur.execute(
            "SELECT UserID FROM Users WHERE OauthID = %s AND OauthProvider = %s",
            (oauth_id, oauth_provider)
        )
        result = cur.fetchone()

        if result:
            user_id = result[0]
            # Update existing user
            cur.execute(
                "UPDATE Users SET username = %s, bio = %s WHERE UserID = %s",
                (username, bio, user_id)
            )
        else:
            # Create new user
            cur.execute(
                "INSERT INTO Users (OauthID, OauthProvider, username, bio, adminFlag) "
                "VALUES (%s, %s, %s, %s, %s) RETURNING UserID",
                (oauth_id, oauth_provider, username, bio, False)
            )
            user_id = cur.fetchone()[0]

        submit_image(userID=user_id, cur=cur)

def update_profile(oauth_id, oauth_provider, username, bio, image_data=None, cur=None):
    """Update existing user profile"""
    with get_db_cursor(commit=True, cur=cur) as cur:
        # Get user ID
        cur.execute(
            "SELECT UserID FROM Users WHERE OauthID = %s AND OauthProvider = %s",
            (oauth_id, oauth_provider)
        )
        result = cur.fetchone()

        if not result:
            # If user doesn't exist, create them instead
            insert_profile_image(oauth_id, oauth_provider, username, bio, image_data)
            return

        user_id = result[0]

        # Update user data
        cur.execute(
            "UPDATE Users SET username = %s, bio = %s WHERE UserID = %s",
            (username, bio, user_id)
        )

        # Handle profile image if provided
        if image_data:
            # Delete existing profile picture
            cur.execute(
                "DELETE FROM Images WHERE UserID = %s AND RecipeID IS NULL",
                (user_id,)
            )
            # Insert new profile picture with sanitized title
            safe_title = f"Profile Picture for User {user_id}"
            cur.execute(
                "INSERT INTO Images (UserID, RecipeID, Title, Link, content) "
                "VALUES (%s, %s, %s, %s, %s)",
                (user_id, None, safe_title, None, image_data)
            )


def get_profile_data(oauth_id, oauth_provider, cur=None):
    with get_db_cursor(commit=False, cur=cur) as cur:
        # Get user data (without image content)
        cur.execute(
            "SELECT UserID, username, bio FROM Users WHERE OauthID = %s AND OauthProvider = %s",
            (oauth_id, oauth_provider)
        )
        user_result = cur.fetchone()

        if not user_result:
            return None

        user_id, username, bio = user_result

        # Check for profile image existence
        cur.execute(
            "SELECT ImageID FROM Images WHERE UserID = %s AND RecipeID IS NULL ORDER BY ImageID DESC LIMIT 1",
            (user_id,)
        )
        image_result = cur.fetchone()

        return {
            "name": username,  # Changed from "username" to "name" to match frontend
            "bio": bio,
            "has_image": image_result is not None
        }


## Image Dealings ##


## Retrieve an image from the db (either bytes or link)
## Retrieves by ID in order of importance
## i.e. select by imageID, recipeID, userID separately, return first result
def get_image(imageID=None, recipeID=None, userID=None, cur=None):

    query = None
    queryArgs = None

    # Query first by imageID
    if imageID != None:
        query = "SELECT content, link FROM Images WHERE imageID = %s"
        queryArgs = imageID
    
    # Then by recipeID
    elif recipeID != None:
        query = "SELECT content, link FROM Images WHERE recipeID = %s"
        queryArgs = recipeID

    # Finally by userID
    # Specify (recipeID IS NULL) for only user profile images
    elif userID != None:
        query = "SELECT content, link FROM Images WHERE userID = %s AND recipeID IS NULL"
        queryArgs = userID
    
    # No ids defined, return none
    else:
        return None
    
    # Do the query
    with get_db_cursor(commit=False, cur=cur) as cur:
        
        cur.execute(query, (queryArgs,))
        res = cur.fetchone()
        
        # Handle output
        if res != None:
            if res[0] != None:
                return bytes(res[0])    # file bytes
            if res[1] != None:
                return res[1]           # url from other site
        return None



## Submit an image to the DB
## ONE of recipeID or userID fields must be specified to submit
##      if recipeID defined - recipe image
##      if only userID defined - profile image
## ONE of data or link must be specified
def submit_image(content=None, title=None, link=None, recipeID=None, userID=None, cur=None):

    # No ID to specify by
    if (recipeID and userID) == None:
        return None

    # No content
    if (link or content) == None:
        return None
    
    with get_db_cursor(commit=True, cur=cur) as cur:
        
        # Find existing imageID
        cur.execute(
            "SELECT imageID FROM images WHERE recipeID = %s AND userID = %s",
            (recipeID, userID)
        )
        imageID = cur.fetchone()

        # Update if imageID exists
        if imageID != None:
            imageID = imageID[0]
            cur.execute(
                "UPDATE images SET title = %s, link = %s, content = %s WHERE imageId = %s",
                (title, link, content, imageID)
            )

        # Insert if no imageID
        else:
            cur.execute(
                """
                INSERT INTO images (
                    recipeID, userID, title, link, content
                )
                VALUES (
                    %s, %s, %s, %s, %s
                )
                """,
                (recipeID, userID, title, link, content)
            )


### Comments ###

    
def get_comments(recipeID, cur=None):
    with get_db_cursor(commit=False, cur=cur) as cur:
        cur.execute(
            """
            SELECT c.commentid, c.recipeid, c.userid, c.content, c.lastedit,
                   c.parentid, u.username
            FROM comments c
            JOIN users u ON u.userid = c.userid
            WHERE c.recipeid = %s
            ORDER BY c.lastedit ASC, c.commentid ASC
            """,
            (recipeID,)
        )
        rows = cur.fetchall()
        return [dict(row) for row in rows]

def add_comment(recipeID, userID, content, parentID=None):
    with get_db_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO comments (recipeid, userid, likes, dislikes, content, parentid)
            VALUES (%s, %s, 0, 0, %s, %s)
            RETURNING commentid, recipeid, userid, content, lastedit, parentid
            """,
            (recipeID, userID, content, parentID)
        )
        row = cur.fetchone()
        cur.execute("SELECT username FROM users WHERE userid = %s", (userID,))
        username = cur.fetchone()[0] if cur.rowcount is not None else None
        out = dict(row)
        out["username"] = username
        return out


def get_user_rating(recipeID, userID, cur=None):
    with get_db_cursor(commit=False, cur=cur) as cur:
        cur.execute(
            "SELECT rating FROM Interactions WHERE recipeID = %s AND userID = %s",
            (recipeID, userID),
        )
        row = cur.fetchone()
        return int(row[0]) if row and row[0] is not None else None


def has_user_rated(recipeID, userID, cur=None):
    with get_db_cursor(commit=False, cur=cur) as cur:
        cur.execute(
            "SELECT 1 FROM Interactions WHERE recipeID = %s AND userID = %s AND rating IS NOT NULL",
            (recipeID, userID),
        )
        return cur.fetchone() is not None

def submit_interact(recipeID, userID, rating=None, saved=None, cur=None):
    try:
        # Delegate to existing internal implementation
        return _submit_interact(recipeID, userID, rating=rating, saved=saved, cur=cur)
    except Exception as e:
        import traceback
        print("db.submit_interact failed:", e)
        traceback.print_exc()
        raise
    
def update_comment(commentID, userID, content, cur=None):
    with get_db_cursor(commit=True, cur=cur) as cur:
        cur.execute(
            """
            UPDATE comments
               SET content = %s, lastedit = NOW()
             WHERE commentid = %s AND userid = %s
         RETURNING commentid, recipeid, userid, content, lastedit
            """,
            (content, commentID, userID),
        )
        row = cur.fetchone()
        if not row:
            return None
        cur.execute("SELECT username FROM users WHERE userid = %s", (userID,))
        uname = (cur.fetchone() or [None])[0]
        out = dict(row)
        out["username"] = uname
        return out

def delete_comment(commentID, userID, cur=None):
    with get_db_cursor(commit=True, cur=cur) as cur:
        cur.execute(
            "DELETE FROM comments WHERE commentid = %s AND userid = %s RETURNING recipeid",
            (commentID, userID),
        )
        return cur.fetchone() is not None


def is_recipe_saved(recipeID, userID, cur=None):
    if not userID:
        return False
    with get_db_cursor(commit=False, cur=cur) as cur:
        cur.execute(
            "SELECT saved FROM Interactions WHERE recipeid=%s AND userid=%s",
            (recipeID, userID),
        )
        row = cur.fetchone()
        return bool(row[0]) if row and row[0] is not None else False

# for browsing so that we only show tags where theres a recipe associated with it 
def get_tag_name():
    with get_db_cursor(commit=False) as cur:
        cur.execute("SELECT DISTINCT t.name FROM tags t JOIN tagmatch tm ON t.tagid = tm.tagid;")
        return ["".join(name) for name in cur.fetchall()]