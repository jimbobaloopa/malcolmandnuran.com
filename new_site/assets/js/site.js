// Mobile menu + photo lightbox. No dependencies.
(function () {
  var toggle = document.querySelector('.nav-toggle');
  var nav = document.getElementById('site-nav');
  if (toggle && nav) {
    toggle.addEventListener('click', function () {
      var open = nav.classList.toggle('open');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }

  var links = Array.prototype.slice.call(document.querySelectorAll('a.photo'));
  if (!links.length) return;

  var box = document.createElement('div');
  box.className = 'lightbox';
  box.hidden = true;
  box.setAttribute('role', 'dialog');
  box.setAttribute('aria-modal', 'true');
  box.innerHTML = '<figure><img alt=""><figcaption></figcaption></figure>' +
    '<button class="lb-close" aria-label="Close">×</button>' +
    '<button class="lb-prev" aria-label="Previous photo">‹</button>' +
    '<button class="lb-next" aria-label="Next photo">›</button>';
  document.body.appendChild(box);
  var img = box.querySelector('img');
  var cap = box.querySelector('figcaption');
  var index = 0;

  function show(i) {
    index = (i + links.length) % links.length;
    var a = links[index];
    img.src = a.href;
    var text = a.getAttribute('data-caption') || '';
    cap.textContent = text;
    cap.hidden = !text;
    box.querySelector('.lb-prev').hidden = box.querySelector('.lb-next').hidden = links.length < 2;
    box.hidden = false;
    document.body.style.overflow = 'hidden';
  }
  function close() {
    box.hidden = true;
    img.removeAttribute('src');
    document.body.style.overflow = '';
    links[index].focus();
  }

  links.forEach(function (a, i) {
    a.addEventListener('click', function (e) { e.preventDefault(); show(i); });
  });
  box.querySelector('.lb-close').addEventListener('click', close);
  box.querySelector('.lb-prev').addEventListener('click', function () { show(index - 1); });
  box.querySelector('.lb-next').addEventListener('click', function () { show(index + 1); });
  box.addEventListener('click', function (e) { if (e.target === box) close(); });
  document.addEventListener('keydown', function (e) {
    if (box.hidden) return;
    if (e.key === 'Escape') close();
    else if (e.key === 'ArrowLeft') show(index - 1);
    else if (e.key === 'ArrowRight') show(index + 1);
  });
})();
