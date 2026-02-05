# Flask + Jinja2 Refined Minimal Design Guide

## Overview

This design guide documents the **Refined Minimal** design system used across all Flask/Jinja2 templates in this project. Follow these guidelines when creating or modifying any template or DOM manipulation via scripts.

**Design Philosophy:** Elegant restraint with precise typography, minimal visual noise, and professional aesthetics optimized for data-heavy applications.

---

## When to Use This Guide

**ALWAYS** apply these standards when:
- ✅ Creating new Jinja2 templates
- ✅ Modifying existing templates
- ✅ Writing JavaScript that manipulates the DOM
- ✅ Adding new UI components
- ✅ Implementing forms, tables, or cards

---

## Technology Stack

### Core Framework
- **Backend**: Python Flask
- **Templating**: Jinja2
- **CSS Approach**: CSS Custom Properties + Tailwind utilities (minimal)
- **Icons**: Heroicons (inline SVG)

### Typography
- **Primary Font**: Inter (Google Fonts)
- **Weights**: 300 (light), 400 (regular), 500 (medium), 600 (semibold), 700 (bold)
- **Font Family**: `'Inter', system-ui, sans-serif`
- **Font Loading**: Preconnect to Google Fonts for performance

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
```

---

## Refined Minimal Design System

### CSS Custom Properties

All templates should include or inherit these CSS variables:

```css
:root {
    /* Text Colors */
    --color-ink: #1a1a1a;              /* Primary text */
    --color-ink-muted: #525252;         /* Secondary text */
    --color-ink-subtle: #8a8a8a;        /* Tertiary text, labels */

    /* Surface Colors */
    --color-surface: #fafafa;           /* Light background */
    --color-surface-warm: #f7f6f3;      /* Page background */

    /* Border Colors */
    --color-border: #e8e6e1;            /* Standard border */
    --color-border-subtle: #f0eeea;     /* Subtle dividers */

    /* Semantic Colors */
    --color-accent: #c9a227;            /* Gold accent */
    --color-accent-muted: rgba(201, 162, 39, 0.12);
    --color-success: #2d6a4f;           /* Green */
    --color-warning: #9a6700;           /* Orange/amber */
    --color-error: #9b2c2c;             /* Red */

    /* Typography */
    --font-display: 'Inter', system-ui, sans-serif;
    --font-body: 'Inter', system-ui, sans-serif;

    /* Easing Functions */
    --ease-out-expo: cubic-bezier(0.16, 1, 0.3, 1);
    --ease-out-quart: cubic-bezier(0.25, 1, 0.5, 1);
}
```

### Global Styles

```css
body {
    background: var(--color-surface-warm);
    font-family: var(--font-body);
    color: var(--color-ink);
}

#main-content {
    background: var(--color-surface-warm);
}
```

---

## Color System

### Primary Text Hierarchy
- **Primary (headlines, values)**: `var(--color-ink)` (#1a1a1a)
- **Secondary (subheadings)**: `var(--color-ink-muted)` (#525252)
- **Tertiary (labels, hints)**: `var(--color-ink-subtle)` (#8a8a8a)

### Surface Colors
- **Page background**: `var(--color-surface-warm)` (#f7f6f3)
- **Card background**: `white` or `var(--color-surface)` (#fafafa)

### Semantic Colors
- **Success**: `var(--color-success)` (#2d6a4f) - with 8% alpha for backgrounds
- **Warning**: `var(--color-warning)` (#9a6700) - with accent-muted for backgrounds
- **Error**: `var(--color-error)` (#9b2c2c) - with 8% alpha for backgrounds
- **Accent**: `var(--color-accent)` (#c9a227) - use sparingly

### Border Colors
- **Standard**: `var(--color-border)` (#e8e6e1) - cards, inputs
- **Subtle**: `var(--color-border-subtle)` (#f0eeea) - table rows, dividers

---

## Typography Scale

### Headings
```css
.refined-page-title {
    font-family: var(--font-display);
    font-size: 1.75rem;        /* 28px */
    font-weight: 600;
    letter-spacing: -0.02em;   /* Tighter tracking for display */
    color: var(--color-ink);
    margin-bottom: 2rem;
}

.refined-card-title {
    font-family: var(--font-display);
    font-size: 1rem;           /* 16px */
    font-weight: 600;
    letter-spacing: -0.01em;
    color: var(--color-ink);
    margin-bottom: 1.25rem;
}
```

### Body Text
```css
.refined-field-value {
    color: var(--color-ink);
    font-weight: 400;
    font-size: 0.9375rem;      /* 15px */
}

.refined-subtitle {
    color: var(--color-ink-muted);
    font-size: 0.8125rem;      /* 13px */
    font-weight: 300;
}
```

### Labels
```css
.refined-label,
.refined-field-label {
    display: block;
    font-size: 0.75rem;        /* 12px - compact */
    /* OR */
    font-size: 0.6875rem;      /* 11px - extra compact for tables */
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.06em;    /* Wide tracking for readability */
    color: var(--color-ink-subtle);
    margin-bottom: 0.5rem;
}
```

---

## Component Patterns

### 1. Cards

#### Standard Card
```html
<div class="refined-card">
    <h2 class="refined-card-title">Card Title</h2>
    <div style="display: flex; flex-direction: column; gap: 1.25rem;">
        <!-- Content -->
    </div>
</div>
```

```css
.refined-card {
    background: white;
    border: 1px solid var(--color-border);
    border-radius: 2px;              /* Minimal, sharp corners */
    padding: 1.5rem;                 /* 24px */
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04); /* Subtle */
}
```

#### Compact Card (for dense layouts)
```html
<div class="refined-card" style="padding: 1rem;">
    <h3 class="refined-card-title" style="margin-bottom: 1rem;">Section</h3>
    <!-- Content -->
</div>
```

---

### 2. Buttons

#### Primary Button
```html
<button class="refined-btn-primary">
    Button Text
</button>
```

```css
.refined-btn-primary {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.625rem 1rem;        /* Compact vertical */
    font-family: var(--font-body);
    font-size: 0.8125rem;
    font-weight: 500;
    letter-spacing: 0.02em;
    background: var(--color-ink);
    color: white;
    border-radius: 2px;
    border: none;
    cursor: pointer;
    transition: all 0.25s var(--ease-out-expo);
}

.refined-btn-primary:hover {
    background: #333;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}
```

#### Secondary Button
```html
<button class="refined-btn-secondary">
    Cancel
</button>
```

```css
.refined-btn-secondary {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.625rem 1rem;
    font-family: var(--font-body);
    font-size: 0.8125rem;
    font-weight: 400;
    background: white;
    color: var(--color-ink-muted);
    border-radius: 2px;
    border: 1px solid var(--color-border);
    cursor: pointer;
    transition: all 0.2s ease;
}

.refined-btn-secondary:hover {
    border-color: var(--color-ink-muted);
    background: var(--color-surface);
}
```

#### Danger Button
```html
<button class="refined-btn-danger">
    Delete
</button>
```

```css
.refined-btn-danger {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.625rem 1rem;
    font-family: var(--font-body);
    font-size: 0.8125rem;
    font-weight: 400;
    background: rgba(155, 44, 44, 0.06);
    color: var(--color-error);
    border-radius: 2px;
    border: 1px solid rgba(155, 44, 44, 0.2);
    cursor: pointer;
    transition: all 0.2s ease;
}

.refined-btn-danger:hover {
    background: rgba(155, 44, 44, 0.1);
}
```

#### Ghost Button (minimal)
```html
<button class="refined-btn-ghost">
    <svg>...</svg>
</button>
```

```css
.refined-btn-ghost {
    background: transparent;
    color: var(--color-ink-muted);
    border: none;
    padding: 0.5rem;
    border-radius: 2px;
    cursor: pointer;
    transition: all 0.2s ease;
}

.refined-btn-ghost:hover {
    color: var(--color-ink);
    background: var(--color-surface);
}
```

---

### 3. Form Elements

#### Text Input
```html
<div>
    <label for="field" class="refined-label">
        Field Label
    </label>
    <input type="text"
           id="field"
           name="field"
           class="refined-input"
           placeholder="Enter value"
           required>
</div>
```

```css
.refined-input {
    width: 100%;
    padding: 0.625rem 1rem;
    font-family: var(--font-body);
    font-size: 0.8125rem;
    font-weight: 300;
    color: var(--color-ink);
    background: white;
    border: 1px solid var(--color-border);
    border-radius: 2px;
    transition: all 0.3s var(--ease-out-expo);
}

.refined-input::placeholder {
    color: var(--color-ink-subtle);
}

.refined-input:focus {
    outline: none;
    border-color: var(--color-ink-muted);
    box-shadow: 0 0 0 3px rgba(26, 26, 26, 0.04);
}
```

#### Select Dropdown
```html
<select name="field" class="refined-input" required>
    <option value="">Select...</option>
    <option value="1">Option 1</option>
</select>
```

#### Checkbox
```html
<div style="display: flex; align-items: center;">
    <input type="checkbox"
           id="field"
           name="field"
           class="refined-checkbox">
    <label for="field" class="refined-checkbox-label">
        Checkbox Label
    </label>
</div>
```

```css
.refined-checkbox {
    margin-right: 0.5rem;
}

.refined-checkbox-label {
    font-size: 0.8125rem;
    color: var(--color-ink-muted);
    font-weight: 300;
}
```

---

### 4. Tables

#### Table Container
```html
<div class="table-container">
    <div class="table-scroll-wrapper">
        <!-- Fixed Header -->
        <table class="refined-table" style="flex-shrink: 0;">
            <colgroup>
                <col class="col-name">
                <col class="col-value">
            </colgroup>
            <thead>
                <tr>
                    <th class="sortable" onclick="sortTable('name')">
                        Column Name
                        <svg class="sort-icon">...</svg>
                    </th>
                    <th>Value</th>
                </tr>
            </thead>
        </table>

        <!-- Scrollable Body -->
        <div class="tbody-scroll">
            <table class="refined-table">
                <colgroup>
                    <col class="col-name">
                    <col class="col-value">
                </colgroup>
                <tbody>
                    <tr class="clickable-row">
                        <td><span class="seller-name">Text</span></td>
                        <td><span class="amount-value">123.45</span></td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>

    <!-- Pagination Footer -->
    <div class="pagination-bar">
        <span class="pagination-info">
            Showing <span class="pagination-count">10</span> of <span class="pagination-count">100</span>
        </span>
    </div>
</div>
```

#### Table Styles
```css
.table-container {
    background: white;
    border: 1px solid var(--color-border);
    border-radius: 2px;
    display: flex;
    flex-direction: column;
    flex: 1;
    min-height: 0;
    overflow: hidden;
}

.table-scroll-wrapper {
    flex: 1;
    min-height: 0;
    overflow: hidden;
    display: flex;
    flex-direction: column;
}

.tbody-scroll {
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
}

.refined-table {
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
}

.refined-table thead {
    background: var(--color-surface);
    position: sticky;
    top: 0;
    z-index: 10;
}

.refined-table th {
    padding: 0.5rem 1rem;
    font-size: 0.6875rem;        /* 11px - compact */
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: var(--color-ink-subtle);
    text-align: left;
    border-bottom: 1px solid var(--color-border);
    white-space: nowrap;
}

.refined-table th.sortable {
    cursor: pointer;
    user-select: none;
    transition: color 0.2s ease;
}

.refined-table th.sortable:hover {
    color: var(--color-ink);
}

.refined-table tbody tr {
    transition: background-color 0.2s ease;
}

.refined-table tbody tr:hover {
    background: var(--color-surface);
}

.refined-table td {
    padding: 0.5rem 1rem;
    font-size: 0.8125rem;
    color: var(--color-ink);
    border-bottom: 1px solid var(--color-border-subtle);
    vertical-align: middle;
}

.refined-table tbody tr:last-child td {
    border-bottom: none;
}
```

#### Column Width Classes
```css
.col-number { width: 14%; }
.col-seller { width: 22%; }
.col-nip { width: 12%; }
.col-date { width: 10%; }
.col-amount { width: 12%; }
.col-status { width: 10%; }
.col-actions { width: 10%; }
```

#### Specialized Cell Styles
```css
/* Invoice number - Primary identifier */
.invoice-number {
    font-family: var(--font-display);
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--color-ink);
    letter-spacing: -0.01em;
}

/* Seller name */
.seller-name {
    font-weight: 400;
    color: var(--color-ink);
    display: block;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

/* NIP - Monospace */
.nip-number {
    font-family: 'SF Mono', 'Fira Code', monospace;
    font-size: 0.75rem;
    color: var(--color-ink-muted);
    letter-spacing: 0.02em;
}

/* Dates */
.date-value {
    color: var(--color-ink-muted);
    font-weight: 300;
}

/* Amount - Emphasized */
.amount-value {
    font-family: var(--font-display);
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--color-ink);
    white-space: nowrap;
}

.currency-code {
    font-family: var(--font-body);
    font-size: 0.75rem;
    font-weight: 400;
    color: var(--color-ink-subtle);
    margin-left: 0.25rem;
}
```

#### Empty State
```html
<div class="empty-state">
    <svg class="empty-icon">...</svg>
    <h3 class="empty-title">No Records</h3>
    <p class="empty-text">
        Add your first record using the button above.
    </p>
</div>
```

```css
.empty-state {
    padding: 3rem 2rem;
    text-align: center;
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
}

.empty-icon {
    width: 4rem;
    height: 4rem;
    margin: 0 auto 1.5rem;
    color: var(--color-ink-subtle);
    opacity: 0.3;
}

.empty-title {
    font-family: var(--font-display);
    font-size: 1.5rem;
    font-weight: 500;
    color: var(--color-ink);
    margin-bottom: 0.5rem;
}

.empty-text {
    color: var(--color-ink-subtle);
    font-size: 0.9375rem;
    font-weight: 300;
    max-width: 320px;
    margin: 0 auto 2rem;
    line-height: 1.6;
}
```

---

### 5. Badges

#### Status Badge
```html
<span class="status-badge status-paid">Paid</span>
<span class="status-badge status-unpaid">Unpaid</span>
<span class="status-badge status-overdue">Overdue</span>
```

```css
.status-badge {
    display: inline-flex;
    align-items: center;
    padding: 0.375rem 0.75rem;
    font-size: 0.6875rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    border-radius: 1px;
}

.status-paid {
    background: rgba(45, 106, 79, 0.08);
    color: var(--color-success);
}

.status-unpaid {
    background: var(--color-accent-muted);
    color: var(--color-warning);
}

.status-overdue {
    background: rgba(155, 44, 44, 0.08);
    color: var(--color-error);
}
```

#### Clickable Badge (for status toggling)
```html
<span class="status-badge clickable-status status-paid"
      onclick="toggleStatus(123)">
    Paid
</span>
```

```css
.clickable-status {
    cursor: pointer;
    transition: all 0.2s ease;
    user-select: none;
}

.clickable-status:hover {
    transform: scale(1.05);
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
}

.clickable-status:active {
    transform: scale(0.98);
}
```

#### Role Badges
```css
.refined-badge {
    display: inline-flex;
    align-items: center;
    padding: 0.375rem 0.75rem;
    font-size: 0.6875rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    border-radius: 1px;
}

.badge-purple { background: rgba(147, 51, 234, 0.08); color: #7e22ce; }
.badge-blue { background: rgba(37, 99, 235, 0.08); color: #1d4ed8; }
.badge-green { background: rgba(45, 106, 79, 0.08); color: var(--color-success); }
.badge-pink { background: rgba(236, 72, 153, 0.08); color: #be185d; }
.badge-red { background: rgba(155, 44, 44, 0.08); color: var(--color-error); }
.badge-gray { background: rgba(107, 114, 128, 0.08); color: #4b5563; }
```

---

### 6. Flash Messages

```html
<div class="flash-message flash-success">
    Success message
</div>
<div class="flash-message flash-error">
    Error message
</div>
<div class="flash-message flash-warning">
    Warning message
</div>
<div class="flash-message flash-info">
    Info message
</div>
```

```css
.flash-message {
    padding: 0.875rem 1rem;
    border-radius: 2px;
    margin-bottom: 1.5rem;
    font-size: 0.8125rem;
}

.flash-success {
    background: rgba(45, 106, 79, 0.08);
    color: var(--color-success);
    border: 1px solid rgba(45, 106, 79, 0.2);
}

.flash-error {
    background: rgba(155, 44, 44, 0.08);
    color: var(--color-error);
    border: 1px solid rgba(155, 44, 44, 0.2);
}

.flash-warning {
    background: rgba(201, 162, 39, 0.12);
    color: var(--color-warning);
    border: 1px solid rgba(201, 162, 39, 0.2);
}

.flash-info {
    background: rgba(23, 162, 184, 0.08);
    color: #0c7489;
    border: 1px solid rgba(23, 162, 184, 0.2);
}
```

---

### 7. Filter Pills

```html
<div class="filter-pills">
    <button class="filter-pill active" data-filter="all">
        All <span class="count">24</span>
    </button>
    <button class="filter-pill" data-filter="paid">
        Paid <span class="count">18</span>
    </button>
    <button class="filter-pill" data-filter="unpaid">
        Unpaid <span class="count">6</span>
    </button>
</div>
```

```css
.filter-pills {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 0.75rem;
    flex-shrink: 0;
}

.filter-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.375rem 0.75rem;
    font-size: 0.6875rem;
    font-weight: 400;
    color: var(--color-ink-muted);
    background: white;
    border: 1px solid var(--color-border);
    border-radius: 999px;        /* Pill shape */
    cursor: pointer;
    transition: all 0.2s ease;
}

.filter-pill:hover {
    border-color: var(--color-ink-muted);
}

.filter-pill.active {
    background: var(--color-ink);
    color: white;
    border-color: var(--color-ink);
}

.filter-pill .count {
    font-weight: 500;
}
```

---

### 8. Search Input

```html
<div class="search-wrapper">
    <svg class="search-icon">...</svg>
    <input type="text"
           class="search-input"
           placeholder="Search by name, number...">
</div>
```

```css
.search-wrapper {
    position: relative;
    flex: 1;
    max-width: 400px;
}

.search-input {
    width: 100%;
    padding: 0.5rem 1rem 0.5rem 2.5rem;
    font-family: var(--font-body);
    font-size: 0.8125rem;
    font-weight: 300;
    color: var(--color-ink);
    background: white;
    border: 1px solid var(--color-border);
    border-radius: 2px;
    transition: all 0.3s var(--ease-out-expo);
}

.search-input::placeholder {
    color: var(--color-ink-subtle);
}

.search-input:focus {
    outline: none;
    border-color: var(--color-ink-muted);
    box-shadow: 0 0 0 3px rgba(26, 26, 26, 0.04);
}

.search-icon {
    position: absolute;
    left: 0.75rem;
    top: 50%;
    transform: translateY(-50%);
    color: var(--color-ink-subtle);
    width: 1rem;
    height: 1rem;
}
```

---

### 9. Dropdown Menu

```html
<div class="dropdown" id="export-dropdown">
    <button class="btn-refined btn-refined-secondary"
            onclick="toggleDropdown('export-dropdown')">
        Export
    </button>
    <div class="dropdown-menu">
        <button class="dropdown-item" onclick="exportExcel()">
            <svg>...</svg>
            Export to Excel
        </button>
        <button class="dropdown-item" onclick="exportCSV()">
            <svg>...</svg>
            Export to CSV
        </button>
    </div>
</div>
```

```css
.dropdown {
    position: relative;
}

.dropdown-menu {
    position: absolute;
    top: 100%;
    right: 0;
    margin-top: 0.5rem;
    min-width: 180px;
    background: white;
    border: 1px solid var(--color-border);
    border-radius: 2px;
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.08);
    opacity: 0;
    visibility: hidden;
    transform: translateY(-4px);
    transition: all 0.2s var(--ease-out-expo);
    z-index: 50;
}

.dropdown.open .dropdown-menu {
    opacity: 1;
    visibility: visible;
    transform: translateY(0);
}

.dropdown-item {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    width: 100%;
    padding: 0.75rem 1rem;
    font-size: 0.8125rem;
    color: var(--color-ink);
    background: none;
    border: none;
    text-align: left;
    cursor: pointer;
    transition: background 0.15s ease;
}

.dropdown-item:hover {
    background: var(--color-surface);
}

.dropdown-item svg {
    width: 1rem;
    height: 1rem;
    color: var(--color-ink-muted);
}
```

---

## Spacing & Layout

### Spacing Scale
- **Extra compact**: `0.25rem` (4px), `0.375rem` (6px), `0.5rem` (8px)
- **Compact**: `0.625rem` (10px), `0.75rem` (12px)
- **Default**: `1rem` (16px), `1.25rem` (20px), `1.5rem` (24px)
- **Comfortable**: `2rem` (32px), `2.5rem` (40px)

### Page Content Spacing
- **Page container padding**: `2rem` (32px)
- **Card stacks**: `gap: 1.5rem` between cards
- **Form field spacing**: `gap: 1.25rem`

### Card Padding
- **Standard card**: `padding: 1.5rem` (24px)
- **Compact card**: `padding: 1rem` (16px)
- **Login card**: `padding: 2.5rem` (40px - for standalone forms)

### Table Cell Padding
- **Header cells**: `padding: 0.5rem 1rem` (8px 16px)
- **Body cells**: `padding: 0.5rem 1rem` (8px 16px)

---

## Border Radius

**Standard**: `border-radius: 2px` for ALL components

This creates the signature minimal, sharp aesthetic:
- Cards: `2px`
- Buttons: `2px`
- Inputs: `2px`
- Badges: `1px` (even sharper)
- Filter pills: `999px` (full rounded - exception)

---

## Shadows

**Philosophy**: Subtle elevation, not dramatic depth

```css
/* Standard card shadow */
box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);

/* Button hover */
box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);

/* Dropdown */
box-shadow: 0 10px 40px rgba(0, 0, 0, 0.08);

/* Focus ring (inputs) */
box-shadow: 0 0 0 3px rgba(26, 26, 26, 0.04);
```

---

## Transitions & Animations

### Standard Transitions
```css
/* Buttons, interactive elements */
transition: all 0.25s var(--ease-out-expo);

/* Hover states */
transition: all 0.2s ease;

/* Input focus */
transition: all 0.3s var(--ease-out-expo);
```

### Fade-in Animation
```css
.fade-in {
    animation: fadeIn 0.4s var(--ease-out-expo) forwards;
}

@keyframes fadeIn {
    from {
        opacity: 0;
        transform: translateY(8px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}
```

### Stagger Animation (for table rows)
```css
.stagger-row {
    opacity: 0;
    animation: fadeIn 0.35s var(--ease-out-expo) forwards;
}

/* In JavaScript: */
style="animation-delay: ${index * 0.03}s"
```

---

## Custom Scrollbar

```css
.tbody-scroll::-webkit-scrollbar {
    width: 6px;
}

.tbody-scroll::-webkit-scrollbar-track {
    background: var(--color-surface);
}

.tbody-scroll::-webkit-scrollbar-thumb {
    background: var(--color-border);
    border-radius: 3px;
}

.tbody-scroll::-webkit-scrollbar-thumb:hover {
    background: var(--color-ink-subtle);
}
```

---

## Interactive Patterns

### 1. Clickable Table Rows

```html
<tr class="clickable-row"
    data-invoice-id="123"
    data-has-pdf="true"
    onclick="handleRowClick(event)">
    <!-- cells -->
</tr>
```

```css
.clickable-row {
    cursor: pointer;
}

.clickable-row:hover {
    background: var(--color-surface) !important;
}
```

```javascript
function handleRowClick(event) {
    // Don't trigger if clicking action buttons
    if (event.target.closest('.row-actions') ||
        event.target.closest('a') ||
        event.target.closest('button')) {
        return;
    }

    const row = event.currentTarget;
    const invoiceId = parseInt(row.dataset.invoiceId);
    const hasPdf = row.dataset.hasPdf === 'true';

    if (hasPdf) {
        window.open(`/api/pdf/${invoiceId}`, '_blank');
    }
}
```

### 2. Inline Status Editing

```html
<span class="status-badge clickable-status status-paid"
      data-invoice-id="123"
      data-current-status="Opłacona"
      onclick="handleStatusClick(event)">
    Paid
</span>
```

```javascript
async function handleStatusClick(event) {
    event.stopPropagation(); // Prevent row click

    const badge = event.currentTarget;
    const invoiceId = parseInt(badge.dataset.invoiceId);
    const currentStatus = badge.dataset.currentStatus;

    // Toggle status
    const newStatus = currentStatus === 'Opłacona' ? 'Nieopłacona' : 'Opłacona';

    // Update via API
    const result = await API.invoices.update(invoiceId, { status: newStatus });

    if (result.success) {
        // Update badge without re-rendering table
        updateStatusBadge(badge, newStatus);
    }
}
```

### 3. Debounced Search

```javascript
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

const searchInput = document.getElementById('search-input');
searchInput.addEventListener('input', debounce((e) => {
    searchQuery = e.target.value.toLowerCase().trim();
    applyFiltersAndRender();
}, 300));
```

---

## Icon Usage

### Icon Library
**Heroicons** (inline SVG, 24x24 viewBox)

### Standard Icon Sizes
```css
.icon-xs { width: 0.75rem; height: 0.75rem; }    /* 12px */
.icon-sm { width: 1rem; height: 1rem; }          /* 16px */
.icon-md { width: 1.125rem; height: 1.125rem; }  /* 18px */
.icon-lg { width: 1.5rem; height: 1.5rem; }      /* 24px */
.icon-xl { width: 2rem; height: 2rem; }          /* 32px */
```

### Icon Colors
- **Default**: `color: var(--color-ink-subtle)`
- **Hover**: `color: var(--color-ink)`
- **In buttons**: Match button text color
- **In badges**: Match badge color

---

## Responsive Design

### Philosophy
Mobile-first with progressive enhancement

### Breakpoints
```css
/* Mobile: Default (no prefix) */
/* Tablet: 768px+ */
@media (max-width: 1024px) {
    .col-nip, .col-due { display: none; }
}

/* Mobile: < 768px */
@media (max-width: 768px) {
    .actions-bar { flex-wrap: wrap; }
    .search-wrapper { max-width: none; order: 3; width: 100%; }
    .row-actions { opacity: 1; } /* Always visible on mobile */
}
```

### Responsive Patterns
```html
<!-- Stacked on mobile, 2 columns on tablet -->
<div class="grid grid-cols-1 md:grid-cols-2" style="gap: 1.5rem;">
```

---

## Page Structure

### Standard Page Layout
```html
{% extends "base.html" %}

{% block title %}Page Title{% endblock %}

{% block extra_css %}
<style>
    /* Refined Minimal CSS variables and styles */
    :root {
        --color-ink: #1a1a1a;
        /* ... all variables ... */
    }

    /* Component styles */
    .refined-card { ... }
    .refined-btn-primary { ... }
</style>
{% endblock %}

{% block content %}
<div class="refined-page fade-in">
    <header class="page-header">
        <h1 class="page-title">Page Title</h1>
    </header>

    <!-- Page content -->
    <div class="refined-card">
        <!-- ... -->
    </div>
</div>
{% endblock %}

{% block extra_scripts %}
<script>
    // Page-specific JavaScript
</script>
{% endblock %}
```

### Standalone Template (e.g., login)
```html
<!DOCTYPE html>
<html lang="pl" class="h-full">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Page Title</title>

    <!-- Tailwind CSS -->
    <link rel="stylesheet" href="{{ url_for('static', filename='css/output.css') }}">

    <!-- Google Fonts: Inter -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">

    <style>
        /* Refined Minimal Design System */
        :root { /* ... variables ... */ }
        body { /* ... */ }
        .refined-card { /* ... */ }
        /* ... all component styles ... */
    </style>
</head>
<body class="h-full flex items-center justify-center">
    <!-- Content -->
</body>
</html>
```

---

## JavaScript Patterns

### Utility Functions

```javascript
// Format date (DD.MM.YY)
function formatDateShort(dateString) {
    if (!dateString) return '—';
    const date = new Date(dateString);
    const day = date.getDate().toString().padStart(2, '0');
    const month = (date.getMonth() + 1).toString().padStart(2, '0');
    const year = date.getFullYear().toString().slice(-2);
    return `${day}.${month}.${year}`;
}

// Format amount (Polish locale)
function formatAmountDisplay(amount) {
    if (amount === null || amount === undefined) return '—';
    return new Intl.NumberFormat('pl-PL', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(amount);
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}
```

### API Wrapper Pattern

```javascript
const API = {
    invoices: {
        getAll: async () => {
            const response = await fetch('/api/invoices');
            return await response.json();
        },
        update: async (id, data) => {
            const response = await fetch(`/api/invoices/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            return await response.json();
        }
    }
};
```

---

## Best Practices

### 1. Consistency
- ✅ Always use `border-radius: 2px` for standard components
- ✅ Always use CSS custom properties for colors (`var(--color-ink)`)
- ✅ Always use `0.8125rem` (13px) for body text
- ✅ Always use uppercase labels with `letter-spacing: 0.06em`

### 2. Typography Hierarchy
- **Page titles**: 1.75rem, font-weight: 600, letter-spacing: -0.02em
- **Card titles**: 1rem, font-weight: 600, letter-spacing: -0.01em
- **Labels**: 0.6875rem (11px), uppercase, letter-spacing: 0.06em
- **Body text**: 0.8125rem (13px), font-weight: 300-400

### 3. Color Usage
- **Text**: Use ink hierarchy (ink → ink-muted → ink-subtle)
- **Backgrounds**: White for cards, surface-warm for pages
- **Borders**: Use border (standard) or border-subtle (dividers)
- **Semantic**: Only use success/warning/error for status, not decorative

### 4. Spacing
- **Between cards**: 1.5rem gap
- **Inside cards**: 1.5rem padding (standard), 1rem (compact)
- **Form fields**: 1.25rem gap
- **Table cells**: 0.5rem 1rem padding

### 5. Interactive Elements
- ✅ Always provide hover states
- ✅ Use `transition: all 0.25s var(--ease-out-expo)` for buttons
- ✅ Use `cursor: pointer` for clickable elements
- ✅ Prevent action bubbling with `event.stopPropagation()`

### 6. Performance
- ✅ Use CSS custom properties for easy theming
- ✅ Minimize inline styles (prefer classes)
- ✅ Use debouncing for search inputs (300ms)
- ✅ Use stagger animations with max delay cap (0.3s)

---

## Summary Checklist

When creating or modifying a template, ensure:

- ✅ CSS custom properties defined in `<style>` or inherited
- ✅ Body background set to `var(--color-surface-warm)`
- ✅ All cards use `.refined-card` with 2px border-radius
- ✅ All buttons use `.refined-btn-primary/secondary/danger`
- ✅ All inputs use `.refined-input` with focus state
- ✅ All labels use `.refined-label` (uppercase, letter-spacing)
- ✅ All status badges use `.status-badge` with semantic colors
- ✅ Flash messages use `.flash-message` with type classes
- ✅ Tables use `.refined-table` with fixed headers
- ✅ Font sizes follow hierarchy (11px labels, 13px body, 16px headings)
- ✅ Transitions use `var(--ease-out-expo)` easing
- ✅ Icons match text color hierarchy
- ✅ Hover states on all interactive elements
- ✅ Responsive breakpoints for mobile/tablet

---

## Version

**Version**: 3.0 (Refined Minimal)
**Framework**: Flask + CSS Custom Properties + Minimal Tailwind
**Last Updated**: 2026-02-05
**Changes**: Complete redesign to refined minimal aesthetic, removed standard Tailwind patterns

---

## Quick Reference

### Color Variables
```css
--color-ink, --color-ink-muted, --color-ink-subtle
--color-surface, --color-surface-warm
--color-border, --color-border-subtle
--color-success, --color-warning, --color-error, --color-accent
```

### Font Sizes
```css
11px (0.6875rem) - Labels, table headers
13px (0.8125rem) - Body text, inputs, buttons
15px (0.9375rem) - Field values
16px (1rem)      - Card titles
28px (1.75rem)   - Page titles
```

### Border Radius
```css
2px  - Standard (cards, buttons, inputs)
1px  - Sharper (badges)
999px - Pills (filters only)
```

### Shadows
```css
0 1px 3px rgba(0,0,0,0.04)      - Cards
0 4px 12px rgba(0,0,0,0.15)     - Button hover
0 0 0 3px rgba(26,26,26,0.04)   - Input focus
0 10px 40px rgba(0,0,0,0.08)    - Dropdowns
```
