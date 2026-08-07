
--- Guide for forms ---
## 1. Semantic Structure and Form Element

### Guidelines

- **DO** use the `<form>` element to wrap interactive controls for data collection.
- **DO** use `method="POST"` for sensitive data and mutations; use `method="GET"` for idempotent requests (e.g., search).
- **DO** specify the `action` attribute for the destination URL.
- **DO** specify a `name` attribute for every form control to identify data on submission.
- **DO** use semantic tags like `<button type="submit">`, `<textarea>`, and `<select>`.
- **DO** use `<fieldset>` and `<legend>` to group related controls.
- **DO** use actionable language on submit buttons (e.g., "Save changes").

- **DON'T** use `GET` for sensitive data (it exposes data in history/logs).
- **DON'T** use generic `<div>` or `<span>` for form controls.
- **DON'T** use `type="button"` for primary submission buttons.
- **DON'T** disable textarea resizing without alternate layout provisions.

### Code Example

```html
<form action="/search" method="GET">
  <fieldset>
    <legend>Search Preferences</legend>
    <label for="q">Query:</label>
    <input type="text" id="q" name="q" required>
    <button type="submit">Search</button>
  </fieldset>
</form>
```

### Selection Control Decision Matrix

| Options Count | Choice Type | Recommended Element | Usability & Accessibility Logic |
| :--- | :--- | :--- | :--- |
| **1ÔÇô5** | Single (Exclusive) | `<input type="radio">` | **Zero-click scanning**: All choices are immediately visible. Faster scan time. |
| **6+** | Single (Exclusive) | `<select>` | **Space conservation**: Use only when vertical space is premium or the list is long. |
| **10+ / Dynamic** | Single (Exclusive) | `<input list="id">` (`<datalist>`) | **Fuzzy Search**: Prevents scrolling fatigue in massive sets (e.g., countries). |
| **Any** | Multi-select | `<input type="checkbox">` | **Standard semantics**: Native non-exclusive toggles. |

**Single-Sentence Mental Model**: "Expose mutually exclusive options as visible radio buttons when choices are fewer than six; use `<select>` only when space is constrained or the list is long."

## 2. Accessible Labeling and State

### Guidelines

- **DO** always associate `<label>` with its input using `for` and `id`.
- **DO** place labels above form controls to enable faster scanning.
- **DO** use visible labels; do not rely on `placeholder` alone.
- **DO** ensure the vertical margin between a label and its input is less than the margin between form groups (**Gestalt Proximity Rule**).
- **DO** use `aria-describedby` to link inputs with help text or error messages.
- **DO** define the `lang` attribute on `<html>` for proper device translation.
- **DO** use non-color visual cues (icons, text) to communicate state (don't rely on color alone).
- **DO** indicate clearly which fields are required.
- **DO** use `aria-live` for dynamic error announcements.

- **DON'T** use `placeholder` as a replacement for labels.
- **DON'T** use `aria-label` as the sole text description if translation is needed.
- **DON'T** disable focus outlines without providing a high-contrast alternative.

### Code Example

```html
<div class="field">
  <label for="username">Username:</label>
  <input type="text" id="username" name="username" aria-describedby="user-help" required>
  <span id="user-help" class="hint">3-12 characters.</span>
</div>

<style>
  input:focus-visible {
    outline: 3px solid #0b57d0;
    outline-offset: 2px;
  }
</style>
```

## 3. Autofill and Input Modes

### Guidelines

- **DO** use the `autocomplete` attribute to specify expected data (e.g., `email`, `tel`, `current-password`, `new-password`).
- **DO** use `inputmode` to optimize on-screen keyboards (e.g., `inputmode="numeric"` for PINs).
- **DO** use `enterkeyhint` to set the Enter key label (e.g., `next`, `done`).
- **DO** use single-field inputs for complex numbers (credit cards, phones) to help autofill.

- **DON'T** use `type="number"` for credit cards or ZIP codes (causes UI scroll issues and removes leading zeros).

### Code Example

```html
<label for="zip">ZIP Code:</label>
<input type="text" id="zip" name="zip" autocomplete="postal-code" inputmode="numeric" pattern="\d{5}">
```

## 4. Constraints and Validation

### Guidelines

- **DO** use native constraints: `required`, `minlength`, `maxlength`, `pattern`.
- **DO** use CSS pseudo-classes `:invalid:user-invalid` for non-intrusive styling.
- **DO** use the ValidityState API (`setCustomValidity`) for custom messaging.

- **DON'T** disable submit buttons to block validation; let users submit and highlight errors. However, **DO** disable the button *after* a valid submission is clicked to prevent double-posts.

### Code Example

```html
<label for="code">Activation Code (4 digits):</label>
<input type="text" id="code" name="code" required pattern="\d{4}">

<script>
  const input = document.getElementById('code');
  input.addEventListener('invalid', () => {
    input.setCustomValidity('Please enter exactly 4 digits.');
  });
  input.addEventListener('input', () => {
    input.setCustomValidity('');
  });
</script>
```

### Validation Event Timing Matrix

| Event Trigger | Phase | Action Allowed | UX / Accessibility Logic |
| :--- | :--- | :--- | :--- |
| **`input`** | Active Typing | **Clear** existing errors only. | **Non-intrusive**: Do not yell at the user before they finish typing. |
| **`blur` / `focusout`** | Exiting Field | **Run** check and show error. | **Contextual validation**: Validate once the user indicates they are "done" with a field. |
| **`submit`** | Final Attempt | **Block** and route focus. | **Final gatekeeper**: Intercepts bad payloads and forces screen reader focus to the summary. |

**Single-Sentence Mental Model**: "Validate on `blur` to avoid premature warnings while typing, and reset error states on `input` as soon as the user attempts a correction."

**Security vs UX Scale**: Client-side validation is for User Experience; Server-side validation is for Security. Never treat browser constraints as a data integrity defense.

## 5. Responsive Design and Typography

### Guidelines

- **DO** use single-column layouts for scanning.
- **DO** set `font-size` to at least `1rem` (16px) to prevent iOS zoom.
- **DO** expand clickable areas for mobile tap targets using padding tricks.
- **DO** ensure tap targets are at least `48px`.
- **DO** use units relative to root (`rem`) and unitless `line-height`.
- **DO** use CSS logical properties (e.g., `margin-inline-start`) for RTL support.

### Code Example

```css
.form-group {
  margin-block-end: 1.5rem;
}

/* Expand clickable tap area without layout shift */
label {
  display: inline-block;
  padding: 10px 0;
  margin: -10px 0;
}

input {
  font-size: 1rem;
  padding: 0.75rem;
  min-height: 48px;
  box-sizing: border-box;
}

@media (pointer: coarse) {
  input {
    min-height: 52px;
  }
}
```

## 6. Styling Form Controls

### Guidelines

- **DO** use `accent-color` for quick branding of native radios/checkboxes.
- **DO** use `appearance: none` for custom dropdown arrows without breaking semantics.
- **DO** ensure inputs are clearly visible with adequate border contrast (e.g., `#ccc` or darker on white backgrounds).
- **DO** hide inputs visually using the canonical `.visually-hidden` recipe (`clip-path: inset(50%)` with 1px dimensions) ÔÇö NOT `display: none`, which removes them from the accessibility tree.

### Code Example

```html
<div class="checkbox-container">
  <input type="checkbox" id="sub" name="sub" class="visually-hidden">
  <label for="sub" class="checkbox-label">Subscribe</label>
</div>

<style>
  .visually-hidden {
    position: absolute;
    clip-path: inset(50%);
    overflow: hidden;
    width: 1px;
    height: 1px;
    margin: -1px;
    padding: 0;
    border: 0;
    white-space: nowrap;
  }
  .checkbox-label::before {
    content: "";
    display: inline-block;
    width: 1.25rem;
    height: 1.25rem;
    border: 2px solid #ccc;
  }
  input:focus-visible + .checkbox-label::before {
    outline: 2px solid #0b57d0;
  }
</style>
```

## 7. JavaScript and AJAX

### Guidelines

- **DO** prevent default navigation on form submit for AJAX (`e.preventDefault()`).
- **DO** use `ValidityState` interfaces for real-time validation checks.
- **DO** use `aria-expanded` and `aria-controls` for dynamic UI reveals.

- **DON'T** block page submission if JS fails; ensure server-side fallback.

### Code Example

```js
form.addEventListener('submit', (e) => {
  e.preventDefault();
  const data = new FormData(form);
  // fetch('/submit', { method: 'POST', body: data });
});
```

## 8. Identity, Payments, and Advanced Security

### Guidelines

- **DO** use `autocomplete="new-password"` for sign-up and `autocomplete="current-password"` for sign-in.
- **DO** allow pasting into password fields.
- **DO** provide a toggle capability allowing users to unmask password input.
- **DO** indicate exact amounts on pay buttons (e.g., "Pay $100").
- **DO** use `autocomplete="cc-number"`, `cc-exp`, `cc-csc`.
- **DO** use HTTPS for all pages.
- **DO** implement cryptographically secure anti-CSRF tokens for mutating actions (POST/PUT/DELETE).
- **DO** sanitize user input (e.g., via DOMPurify) before injecting it into the DOM to prevent XSS.
- **DO** implement spam protection (honeypots or CAPTCHA) for open forms.

- **DON'T** utilize HTTP `GET` for endpoints executing state changes.
- **DON'T** use inline JavaScript (e.g., `onclick="..."`) directly within form markup to satisfy strict Content Security Policies (CSP).

### Code Example

```html
<form method="post">
  <input type="hidden" name="csrf_token" value="secure_token_abc123">

  <h1>Sign up</h1>

  <div class="form-group">        
    <label for="name">Full name</label>
    <input id="name" name="name" autocomplete="name" required pattern="[\p{L}\.\- ]+">
  </div>

  <div class="form-group">        
    <label for="email">Email</label>
    <input id="email" name="email" type="email" autocomplete="username" required>
  </div>

  <div class="form-group">
    <label for="password">Password</label>
    <button id="toggle-password" type="button" aria-pressed="false" aria-label="Show password" aria-describedby="toggle-warning">
      <img class="icon-eye" src="/icons/eye.svg" alt="" width="20" height="20">
      <img class="icon-eye-off" src="/icons/eye-off.svg" alt="" width="20" height="20">
    </button>
    <span id="toggle-warning" class="visually-hidden">Warning: this will display your password on the screen.</span>
    <input id="password" name="password" type="password" autocomplete="new-password" minlength="8" aria-describedby="password-constraints" required>
    <div id="password-constraints">Eight or more characters.</div>
  </div>

  <button id="sign-up">Sign up</button>
</form>
```


## 9. Address Collection

### Guidelines

- **DO** use a single field for names.
- **DO** use `autocomplete="street-address"`.
- If the site has users in different countries, **DO** use the `<textarea>` element for addresses, to accommodate different address formats in different geographical regions. If the form uses separate inputs for address parts (e.g. Street, City), **DO** use `autocomplete` values `address-line1`, `address-line2`, etc.
- **DO** make postal codes optional.

- **DON'T** split name inputs into rigid variables ("First", "Last") for global audiences.
- **DON'T** enforce Latin-only characters for names and usernames.

### Code Example

```html
<!-- Accessible Address Form with Autofill -->
<form action="/save-address" method="POST">
  <div class="form-group">
    <label for="full-name">Full name</label>
    <input type="text" id="full-name" name="full_name" maxlength="100" required autocomplete="name">
  </div>

  <div class="form-group">
    <label for="address">Address</label>
    <textarea id="address" name="address" required autocomplete="street-address" maxlength="300"></textarea>
  </div>

  <button type="submit">Save Address</button>
</form>
```


## 10. Usability Testing and Analytics

### Guidelines

- **DO** test forms across multiple devices, browsers, and screen sizes.
- **DO** test keyboard-only navigation (using `Tab` and `Shift+Tab`) and verify visual focus.
- **DO** emulate various impairments (visual, motor) using browser tools.
- **DO** use analytics to monitor form completion rates and bounce points.
- **DO** track discrete events (e.g., field focus, click) to find micro-friction points.

- **DON'T** rely solely on automated tools (Lighthouse) for usability; test with real users.
- **DON'T** track sensitive personal data in standard event labels.

### Code Example

```html
<form action="/submit" method="POST" id="track-form">
  <label for="postal-code">ZIP or postal code</label>
  <input type="text" id="postal-code" name="postal-code" autocomplete="postal-code" maxlength="20" required>
  <button type="submit" id="submit-btn">Submit</button>
</form>

<script>
  const trackForm = document.getElementById('track-form');
  const trackBtn = document.getElementById('submit-btn');
  
  trackBtn.addEventListener('click', () => {
    console.log('Analytics Event: Submit clicked');
  });
</script>
```

## 11. Multi-Page Forms

### Guidelines

- **DO** clearly display progress through a multi-page form with clear labels and progress indicators.
- **DO** allow users to navigate backwards and forwards between pages.
- **DO** use context-specific `enterkeyhint` values (e.g., `"previous"`, `"next"`) to guide navigation via on-screen keyboards.
- **DO** design layouts so that the mobile keyboard does not obscure inputs or buttons (e.g., by placing them in the upper half of the viewport when focused or using CSS scroll-padding).

### Code Example

```html
<nav aria-label="Progress">
  <ol class="progress-tracker">
    <li class="step-done">Step 1: Account</li>
    <li class="step-active" aria-current="step">Step 2: Shipping</li>
    <li class="step-todo">Step 3: Payment</li>
  </ol>
</nav>

<button type="button" onclick="history.back()" enterkeyhint="previous">Previous</button>
<button type="submit" enterkeyhint="next">Next</button>
```


--- Guide for html ---
## Table of Contents

1. Fundamental Semantics and Validation
2. Content Grouping and Attribution
3. Resource Prioritization and Performance
4. Native Overlays: Dialogs and Popovers
5. Disclosures: Details and Summary
6. Focus Boundaries and Visibility
7. HTML APIs and Forms Grouping
8. Native Media Elements
9. Dynamic Styles and Interactivity

## 1. Fundamental Semantics and Validation

### Guidelines

- **DO** use the standard HTML5 doctype `<!DOCTYPE html>` to prevent quirky rendering modes. 
- **DO** set the `lang` attribute on the `<html>` element for screen reader pronunciation and translation tools.
- **DO** use the `<meta name="viewport">` element with the `content` attribute set to `"width=device-width, initial-scale=1.0"` to ensure page responsiveness.
- **DO** use a single `<h1>` per page/view representing the main topic. Exceptions can be made for modal dialogs, which can also use a single `<h1>`.
- **DO** maintain a sequential, non-skipping heading hierarchy (`<h2>` to `<h3>`, but not `<h2>` to `<h4>`).
- **DO** use semantic landmarks (`<header>`, `<nav>`, `<main>`, `<aside>`, `<footer>`) to create regional navigation for assistive technologies.
- **DO** use `<search>` to enclose search and filtering mechanisms (eliminates the need for `role="search"`).
- **DO** use `<button>` for triggered actions (JS, Modals, Forms) and `<a>` strictly for URL navigation. Set `type="button"` for non-submit buttons in forms to prevent unintended submission.
- **DO** use `<ul>`, `<ol>`, and `<dl>` elements for list content. 
- **DO** ensure that all interactive elements like links and buttons have accessible names.  
- **DO** hide purely decorative SVG images from assistive technology using `aria-hidden="true"`. If using a decorative `<img>`, always include an empty `alt` attribute (e.g. `alt=""`). 
- **DO** ensure that informative SVGs like logos, data visualizations, or icon buttons have a proper accessible name. 

- **DON'T** use generic `<div>` or `<span>` when semantic elements exist, for instance for interactive elements, headings, or independently reusable self-contained content.
- **DON'T** use boolean attributes with redundant values (e.g., use `disabled`, not `disabled="disabled"`).
- **DON'T** use generic elements with added ARIA roles or states when native elements with built-in semantics and behavior exist.
- **DON'T** change the native semantics of elements with ARIA unless it is a critical requirement. 
- **DON'T** use `role="presentation"` or `aria-hidden="true"` on focusable elements or their parents and ancestors. 
- **DON'T** disable page zooming capabilities.

### Code Example

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Dashboard | Platform</title>
</head>
<body>
  <header>
    <nav>
      <ul>
        <li><a href="#">About</a></li>
        <li><a href="#">Contact</a></li>
      </ul>
    </nav>
  </header>
  <main>
     <h1>Analytics</h1>
    <search>
      <form action="/filter" method="GET">
        <label for="search-input">Scan items:</label>
        <input type="search" id="search-input" name="q">
        <button type="submit">Search</button>
      </form>
    </search>
    <article>
      <h2>First post</h2>
    </article>
  </main>
</body>
</html>
```

## 2. Content Grouping and Attribution

### Guidelines

- **DO** use `<blockquote>` for extended quotations from another source, and use the `cite` attribute to provide a machine-readable URL for that source.
- **DO** use `<figure>` to group self-contained content (images, code snippets, or quotes) that is referenced from the main flow but could be moved to an appendix or sidebar without affecting the document's meaning.
- **DO** use `<figcaption>` as the first or last child of a `<figure>` to provide a human-readable caption or attribution.
- **DO** use the `<cite>` element inside a caption or attribution to identify the **title** of a work (e.g., a book or website name), not the author's name.
- **DO** use the `<code>` element for short fragments of computer code (e.g., variable names, file paths, or inline snippets).
- **DO** wrap `<code>` inside a `<pre>` element when displaying blocks of code to preserve whitespace and line breaks.
- **DO** ensure that code blocks are accessible by adding `tabindex="0"` to the `<pre>` element if it becomes scrollable, allowing keyboard users to reach the content.

- **DON'T** use `<blockquote>` for purely visual indentation of non-quoted text.
- **DON'T** use `<figure>` for every single image; use it only when a caption is required or when the content is a distinct, referenced unit.
- **DON'T** use `<pre>` without `<code>` for code blocks; `<pre>` alone only preserves formatting but doesn't convey that the content is a computer language.

### Code Example

```html
<!-- Quote with attribution using Figure -->
<figure>
  <blockquote cite="https://html.spec.whatwg.org/">
    <p>The figure element represents some flow content, optionally with a caption, that is self-contained and is typically referenced as a single unit from the main flow of the document.</p>
  </blockquote>
  <figcaption>
    Definition of the &lt;figure&gt; element from the <cite>HTML Living Standard</cite>
  </figcaption>
</figure>

<!-- Image with caption -->
<figure>
  <img 
    src="architecture-diagram.webp" 
    alt="Diagram showing the flow between Client, API Gateway, and Microservices"
    width="800"
    height="450"
    loading="lazy"
  >
  <figcaption>Figure 1: High-level system architecture overview.</figcaption>
</figure>

<!-- Code block with accessibility and language hint -->
<figure>
  <figcaption>Example configuration:</figcaption>
  <pre tabindex="0"><code class="language-json">
{
  "name": "gemini-cli",
  "version": "1.0.0",
  "private": true
}
  </code></pre>
</figure>

<!-- Inline code -->
<p>To initialize the project, run the <code>npm install</code> command.</p>
```

## 3. Resource Prioritization and Performance

### Guidelines

- **DO** use `fetchpriority="high"` for the Largest Contentful Paint (LCP) element (e.g., hero image) to elevate network priority.
- **DO** use `<link rel="preload" as="image">` with `fetchpriority="high"` for LCP background images defined in CSS.
- **DO** apply `loading="lazy"` to off-screen images and iframes to defer bandwidth.
- **DO** specify `width` and `height` on all `<img>` tags to preserve aspect ratio and prevent Layout Shifts (CLS).
- **DO** use the `srcset` attribute on `<img>`s for adding multiple versions of the same image at different sizes.
- **DO** use the `<picture>` element with a fallback `<img>` for more fine-grained image control like switching between image formats, image sizes, and cropping images at different device sizes. 

- **DON'T** apply `loading="lazy"` to above-the-fold or hero images. This delays LCP.
- **DON'T** overuse `fetchpriority="high"`; prioritization is a zero-sum mechanism. Use `fetchpriority="low"` to demote non-critical trackers or later carousel items.

### Code Example

```html
<!-- High-priority hero image with responsive sizes -->
<img 
  src="hero-large.webp" 
  srcset="hero-small.webp 480w, hero-medium.webp 800w, hero-large.webp 1200w"
  sizes="(max-width: 600px) 100vw, (max-width: 1200px) 80vw, 70vw"
  alt="Main product view" 
  fetchpriority="high" 
  width="1200" 
  height="600"
>

<!-- Art direction and format switching with <picture> -->
<picture>
  <!-- Mobile Art Direction: Different aspect ratio (square) and format (AVIF) -->
  <source 
    media="(max-width: 600px)" 
    srcset="hero-mobile.avif 1x, hero-mobile-2x.avif 2x" 
    type="image/avif"
    width="600" 
    height="600"
  >
  <source 
    media="(max-width: 600px)" 
    srcset="hero-mobile.webp 1x, hero-mobile-2x.webp 2x"
    width="600" 
    height="600"
  >
  
  <!-- Desktop: Modern format for primary layout -->
  <source srcset="hero-desktop.avif" type="image/avif">

  <!-- Fallback img defines the default aspect ratio (2:1) -->
  <img 
    src="hero-desktop.webp" 
    alt="Platform dashboard overview" 
    width="1200" 
    height="600"
    loading="lazy"
  >
</picture>

<!-- Low-priority decorative footer image -->
<img 
  src="footer-art.png" 
  alt="" 
  loading="lazy" 
  width="200" 
  height="100"
>
```

## 4. Native Overlays: Dialogs and Popovers

### Guidelines

See `declarative-dialog-popover-control` (via `npx -y modern-web-guidance@latest retrieve "declarative-dialog-popover-control"`) for more info on fallback strategies for using the Popover API in a cross-browser way.
- **DO** use `<dialog>` for modal overlays (requires JS `.showModal()`) to automatically trap focus, dim backgrounds, and support dismissing via `Esc`. Use the `closedby="any"` attribute to enable native "light-dismiss" (closing on backdrop click) without custom JavaScript.
- **DO** utilize the Popover API (`popover` attribute) for non-modal UI (menus, tooltips) that do not require focus traps.
- **DO** use `::backdrop` to style modal backgrounds.
- **DO** use `<form method="dialog">` to dismiss dialogs without manual JS handlers. Combined button `formmethod="dialog"` yields the button's value to the dialog `.returnValue`.

- **DON'T** use `show()` for modals where keyboard traps are expected (use `showModal()`).
- **DON'T** call `showModal()` on elements possessing a `popover` attribute (they are mutually exclusive programmatic states). However, `<dialog popover="auto">` is a valid declarative architecture to combine dialog semantics with light-dismiss mechanics.

### Code Example

```html
<!-- Popover (No JS required for toggle) -->
<button popovertarget="help-menu">Info</button>
<div id="help-menu" popover="auto">
  <p>Standard help text.</p>
</div>

<!-- Modal Dialog with Form-based closing -->
<button id="show-dialog">Open dialog</button>
<dialog id="fav-modal">
  <!-- method="dialog" closes the dialog natively and sets the returnValue -->
  <form method="dialog">
    <p>Confirm action?</p>
    <button value="cancel">Cancel</button>
    <button value="confirm">Confirm</button>
  </form>
</dialog>

<script>
  const dialog = document.getElementById("fav-modal");
  const openModal = document.getElementById("show-dialog");
  
  // Show modal dialog
  openModal.addEventListener('click', () => dialog.showModal());
  
  // Listen for the 'close' event to retrieve the user's choice (returnValue)
  dialog.addEventListener('close', () => {
    console.log(dialog.returnValue); // "confirm" or "cancel"
  });
</script>
```

### Native UI Overlay & Disclosure Matrix

| Feature | Modality | Focus | Dismiss Mechanism | Use Case |
| :--- | :--- | :--- | :--- | :--- |
| **`<dialog>`** | Modal / Non-modal | Automatic trap (Modal) | Esc / Form / `closedby` | Critical Actions, Settings |
| **`[popover]`** | Non-modal | Standard Tab flow | Light-dismiss (Click outside) | Menus, Tooltips, Toasts |
| **`<details>`** | Inline Disclosure | Standard Tab flow | Toggle summary | Accordions, FAQs |

**Heuristic Rule**: Use `<dialog>` for interruptions requiring user action, `popover` for transient info, and `<details>` for inline content expansion.

## 5. Disclosures: Details and Summary

### Guidelines

- **DO** use `<details>` and `<summary>` for native accordions or revealable content without JS.
- **DO** place `<summary>` as the *first* child of `<details>`.
- If headings must be used within a `<summary>`, consider if the heading is essential for understanding or navigating the document structure. If it is, use a more robust disclosure approach that allows wrapping the disclosure trigger with the heading (e.g. `<h2><button type="button" aria-expanded="false" aria-controls="significant-section-content">Significant section</button></h2>`). This ensures the heading semantics arenÔÇÖt lost, and the button and its state are announced.
- **DO** use `details[open]` attribute for styling expanded states.
- **DO** use `details::details-content` for styling the contents of the `<details>` element.
- **DO** use the `name` attribute on multiple `<details>` elements to create exclusive accordions (opening one closes others).

- **DON'T** nest other interactive elements (links, buttons) directly inside `<summary>` text as it acts as a button and breaks focus.
- **DON'T** hide visible triangles via `list-style: none` without providing explicit directional cues (via `::before`/`::after` pseudo-elements).
- **DON'T** use the `title` attribute to create tooltip effects. 

### Code Example

```html
<!-- Exclusive Accordion Set -->
<details name="faq">
  <summary>Item 1</summary>
  <p>Contents...</p>
</details>
<details name="faq">
  <summary>Item 2</summary>
  <p>Contents...</p>
</details>
```

## 6. Focus Boundaries and Visibility

### Guidelines

- **DO** use the global `inert` attribute for entire hidden sections (off-screen menus, background while custom modal is open) to remove them from tab flows and accessibility trees.
- **DO** pair `[inert]` with CSS (`opacity: 0.5`) to visually signify inactivity.
- **DO** rely on natural DOM order for sequential navigation. 

- **DON'T** use positive `tabindex` values (e.g., `1`, `2`). Use `0` to add element to tab flow, or `-1` for JS program focus.
- **DON'T** alter focus flow using CSS properties (`flex-flow: row-reverse`, `order`) without aligning the DOM structure.
- **DON'T** use `node.focus({ preventScroll: true })` without usability validation; it can hide the focused element off-screen.

### Code Example

```html
<!-- De-tabbing a background app shell while custom drawer is open -->
<main id="app-shell" inert>
  <a href="/">Dashboard</a>
</main>
<aside id="drawer">
  <button>Close</button>
</aside>
```

```css
[inert], [inert] * {
  opacity: 0.5;
  cursor: default;
  user-select: none;
}
```

## 7. HTML APIs and Forms Grouping

### Guidelines

See `forms` (via `npx -y modern-web-guidance@latest retrieve "forms"`) for more details on creating modern web forms.

- **DO** utilize the `form="form-id"` attribute to decouple inputs from the physical `<form>` tree.
- **DO** use `<datalist>` coupled with `<input list="id">` for lightweight auto-suggestions (note: visually unstylable and has screen-reader quirks). 
- **DON'T** use `autocomplete="off"` on credential, address, payment, or contact fields. Browsers and password managers ignore it there by design. Use a specific token instead (`autocomplete="email"`, `"street-address"`, `"cc-number"`, etc.).
- **DON'T** use `autocomplete="off"` unless handling highly sensitive tracking tokens (violates standard password manager overrides). Use standard inputs `type="email"`, `type="tel"`.
- **DO** distinguish `autocomplete="current-password"` (sign-in) from `autocomplete="new-password"` (registration / password change) so password managers offer the right action.                                                    
- **DO** match `autocomplete` tokens with appropriate `inputmode` and `type` (`type="email"` + `inputmode="email"` + `autocomplete="email"`). They control different things ÔÇö keyboard, validation, and autofill respectively ÔÇö and reinforce each other.

### Code Example

```html
<form>
  <fieldset>
    <legend>Address Information</legend>
    <label for="city">City:</label>
    <input type="text" id="city" list="cities" autocomplete="address-level2">
    <datalist id="cities">
      <option value="New York">
      <option value="London">
    </datalist>
  </fieldset>
</form>
```

## 8. Native Media Elements

### Guidelines

- **DO** set `width` and `height` to prevent layout shifts (CLS) on `<video>` elements.
- **DO** provide a `poster` image fallback for videos.
- **DO** include subtitles and captions with `<track>`.
- **DO** ensure background videos are `muted`, provide users with full control over playback, and use `role="none"` or `aria-hidden="true"`. The `controls` attribute must also be omitted to make sure the video is not focusable.  

- **DON'T** rely on JS for basic video controls if native `controls` attribute is sufficient.
- **DON'T** apply `role="none"` or `aria-hidden="true"` to focusable elements (such as embedded interactive `<iframe>` components). Hiding elements from the assistive technology tree while leaving them accessible to sequential keyboard navigation violates core accessibility heuristics. The background video exception holds solely because omitting the `controls` attribute renders the `<video>` element fully non-focusable.

### Code Example

```html
<video 
  controls 
  width="800" 
  height="450" 
  poster="poster.webp"
>
  <source src="intro.webm" type="video/webm">
  <source src="intro.mp4" type="video/mp4">
  <track src="caps.vtt" kind="captions" srclang="en" label="English">
</video>
```

## 9. Dynamic Styles and Interactivity

### Guidelines
- **DO** use the `style` attribute to pass state to CSS via **Custom Properties**. This keeps visual logic in your stylesheet while JavaScript provides the raw data.

- **DON'T** use inline styles for static design (colors, padding, margins) that belong in a stylesheet.
- **DON'T** use inline event handlers (e.g., `onclick`). Trigger actions using `addEventListener()`.

### Code Example

```html
<body>
  <!-- Progress with style-driven color data -->
  <label for="upload-progress">Upload status:</label>
  <progress id="upload-progress" class="loading-bar" value="0" max="100" style="--brand-hue: 200;"></progress>

  <script>
    const updateProgress = (percent, hue) => {
      const bar = document.querySelector('.loading-bar');
      bar.value = percent;
      
      // Update dynamic style variable 
      if (hue) bar.style.setProperty('--brand-hue', hue);
    };

    // Example: Move to 85% and shift color to green (120)
    setTimeout(() => updateProgress(85, 120), 1000);
  </script>
</body>
```
```css
.loading-bar {
  accent-color: hsl(var(--brand-hue, 200) 80% 50%);
  transition: accent-color 0.3s ease;
}
```

