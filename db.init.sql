

-- GOAL (recipes, users, recipe tags, comments, users, pictures?)

-- Example queries
--  GET ALL RECIPES WITH TAG "TAG"
--  GET ALL COMMENTS ON RECIPE "RECIPE"
--  GET ALL RECIPES FROM USER "USER"


-- USERS

CREATE TABLE Users (
    UserID SERIAL PRIMARY KEY,
    OauthID VARCHAR(255) NOT NULL,   -- OAUTH user.sub field
    OauthProvider VARCHAR(63) NOT NULL,
    adminFlag BOOLEAN,
    username VARCHAR(31),
    bio VARCHAR(255),
    UNIQUE (OauthID, OauthProvider)
);


-- RECIPES and TAGS

CREATE TABLE Recipes (
    RecipeID SERIAL PRIMARY KEY,
    UserID INT,
    draft BOOLEAN NOT NULL,
    servings INT,
    cookTime INT,
    kcal INT,
    title VARCHAR(127),
    brief VARCHAR(255),
    comment VARCHAR(255),
    link VARCHAR(255),
    lastEdit TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    steps JSONB,        -- LIMIT SIZE ON FRONT END
    ingredients JSONB,
    nutrients JSONB,
    FOREIGN KEY (UserID) REFERENCES Users(UserID) ON DELETE SET NULL  -- DELETE on CASCADE?
);

CREATE TABLE Tags (
    tagID SERIAL PRIMARY KEY,       -- SHOULD THIS BE A STRING?
    name VARCHAR(32) UNIQUE
);

CREATE TABLE TagMatch (
    RecipeID INT,
    TagID INT,
    PRIMARY KEY (RecipeID, TagID),
    FOREIGN KEY (RecipeID) REFERENCES Recipes(RecipeID) ON DELETE CASCADE,
    FOREIGN KEY (TagID) REFERENCES Tags(TagID) ON DELETE CASCADE
);

-- EXAMPLE GET BREAKFAST RECIPES QUERY
-- SELECT * 
-- FROM Recipes r
-- JOIN TagMatch tm ON r.RecipeID = tm.RecipeID
-- JOIN Tags t ON tm.TagID = t.TagID
-- WHERE t.name = 'Breakfast'

-- CREATE TABLE nutrition (
--     recipeID INT,
--     accepted JSONB,
--     rejected JSONB,
--     PRIMARY KEY (recipeID) ON DELETE CASCADE
-- )


-- INTERACTIONS

-- PREVIOUSLY 'Likes' and 'Ratings'
CREATE TABLE Interactions (
    recipeID INT,
    userID INT,
    rating INT,
    saved BOOLEAN,
    PRIMARY KEY (recipeID, userID),
    FOREIGN KEY (recipeID) REFERENCES Recipes(recipeID) ON DELETE CASCADE,
    FOREIGN KEY (userID) REFERENCES Users(userID)  -- ON DELETE SET NULL??  issues with composite key?
);


-- COMMENTS

CREATE TABLE Comments (
    CommentID SERIAL,
    RecipeID INT,
    UserID INT,
    likes INT,
    dislikes INT,
    content VARCHAR(1023),
    lastEdit TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    parentid INT,
    PRIMARY KEY (RecipeID, CommentID),
    FOREIGN KEY (RecipeID) REFERENCES Recipes(RecipeID) ON DELETE CASCADE,
    FOREIGN KEY (UserID) REFERENCES Users(UserID)
);


-- IMAGES 

-- PYTHON PILLOW FOR LOWERING FILE SIZE??
CREATE TABLE Images (
    ImageID SERIAL PRIMARY KEY,
    UserID INT,
    RecipeID INT,
    Title VARCHAR(31),
    Link VARCHAR(511),
    content BYTEA,
    FOREIGN KEY (UserID) REFERENCES Users(UserID) ON DELETE CASCADE,
    FOREIGN KEY (RecipeID) REFERENCES Recipes(RecipeID) ON DELETE CASCADE
);


-- INSERT DATA (tags)
-- Record tagID and put into dp.py
TRUNCATE TABLE TAGS RESTART IDENTITY CASCADE;
INSERT INTO tags (name)
VALUES
  ('air-fryer'),
  ('appetizer'),
  ('baking'),
  ('beef'),
  ('bread'),
  ('breakfast'),
  ('brunch'),
  ('budget'),
  ('chicken'),
  ('classic'),
  ('comfort'),
  ('dairy-free'),
  ('dessert'),
  ('dinner'),
  ('easy'),
  ('family-friendly'),
  ('fresh'),
  ('gluten-free'),
  ('grilling'),
  ('healthy'),
  ('high-protein'),
  ('holiday'),
  ('instant-pot'),
  ('kid-friendly'),
  ('lunch'),
  ('low-carb'),
  ('main-course'),
  ('meal-prep'),
  ('modern'),
  ('one-pot'),
  ('pasta'),
  ('pork'),
  ('quick'),
  ('rice'),
  ('salad'),
  ('seafood'),
  ('side-dish'),
  ('slow-cooker'),
  ('snack'),
  ('soup'),
  ('spicy'),
  ('summer'),
  ('vegan'),
  ('vegetarian'),
  ('winter')
RETURNING TAGID, NAME;