# New Tarpeena Tales

Each tale is a plain-text `.txt` file in this folder. They're added to Volume 4 in date order.

```
title: A Tiger by its Tail
date: 2026-10-05

First paragraph. Leave a blank line between paragraphs.

Words in *stars* come out in italics, and **double stars** in bold.

photo: tiger.jpg | The caption shown under the photo
```

Put any photos in this folder next to the `.txt` file. Name files starting with the date
(e.g. `2026-10-05-a-tiger.txt`) so they stay in order.

Then run `python3 build/build_site.py`, commit, and push. GitHub publishes the site a minute or two later.
