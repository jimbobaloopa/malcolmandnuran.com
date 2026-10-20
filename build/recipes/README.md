# New Recipes

Each recipe is a plain-text `.txt` file in this folder. It's added to the end of its category on the recipes page.

```
title: Lamb Rogan Josh
category: Curries + Sides

**Ingredients**

- 1 kg diced lamb
- 2 onions, sliced
- 2 tablespoons curry paste

**Method**

Brown the onions, add the paste and cook for a minute. Leave a blank line between paragraphs.

Words in *stars* come out in italics, and **double stars** in bold.
Lines in a block that all start with "- " become a bulleted list.

photo: rogan-josh.jpg | The caption shown under the photo
```

The category should be one already on the recipes page:
- Curries + Sides,
- Mains, 
- Marinades, 
- Sauces,
- Pastries & Pies,
- Biscuits,
- Salads,
- Sweets,
- John's Cocktails.
(Capitals don't matter. A new name makes a new category at the end of the page.)

Put any photos in this folder next to the `.txt` file. Within a category, recipes appear in file-name order.

Then run `python3 build/build_site.py`, commit, and push. GitHub publishes the site a minute or two later.
