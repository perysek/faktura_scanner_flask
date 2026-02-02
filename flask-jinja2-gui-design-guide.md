# Flask + Jinja2 GUI Design Guide

## Overview

This design guide documents the GUI patterns, styling conventions, and component structures used in the Flask/Jinja2 web application. Follow these guidelines to ensure consistent design and user experience across all new projects.

---

## Technology Stack

### Core Framework
- **Backend**: Python Flask
- **Templating**: Jinja2
- **CSS Framework**: Tailwind CSS (CDN)
- **Icons**: Heroicons (inline SVG)

### Typography
- **Primary Font**: Inter (Google Fonts)
- **Weights**: 300, 400, 500, 600, 700
- **Font Family**: `['Inter', 'system-ui', 'sans-serif']`
- **Font Loading**: Preconnect to Google Fonts for performance

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
```

---

## Color System

### Primary Colors (Blue)
```javascript
primary: {
    50: '#eff6ff',
    100: '#dbeafe',
    200: '#bfdbfe',
    300: '#93c5fd',
    400: '#60a5fa',
    500: '#3b82f6',  // Main primary
    600: '#2563eb',
    700: '#1d4ed8',
    800: '#1e40af',
    900: '#1e3a8a',
}
```

### Accent Colors (Green/Emerald)
```javascript
accent: {
    400: '#34d399',
    500: '#10b981',  // Main accent
    600: '#059669',
}
```

### Semantic Colors
- **Success**: Emerald (`emerald-50`, `emerald-500`, `emerald-700`)
- **Error**: Red (`red-50`, `red-500`, `red-600`)
- **Warning**: Amber (`amber-50`, `amber-500`, `amber-600`)
- **Info**: Blue (`blue-50`, `blue-500`, `blue-800`)

### Neutral Colors (Slate)
- **Background**: `slate-50`, `slate-100`
- **Text Primary**: `slate-800`
- **Text Secondary**: `slate-600`, `slate-500`
- **Borders**: `slate-200`, `slate-300`
- **Sidebar**: `slate-800`, `slate-850`, `slate-900`

---

## Layout Structure

### HTML Base Structure
```html
<html lang="pl" class="h-full">
<body class="h-full bg-gradient-to-br from-slate-50 to-slate-100 font-sans antialiased">
    <div class="flex h-full">
        <!-- Sidebar -->
        <aside class="w-64">...</aside>
        
        <!-- Main Content -->
        <div class="flex-1 flex flex-col min-h-screen overflow-hidden">
            <!-- Header -->
            <header>...</header>
            
            <!-- Flash Messages -->
            <div>...</div>
            
            <!-- Page Content -->
            <main class="flex-1 overflow-auto p-2">...</main>
            
            <!-- Footer -->
            <footer>...</footer>
        </div>
    </div>
</body>
</html>
```

### Sidebar Design
- **Width**: `w-64` (256px)
- **Background**: `bg-gradient-to-b from-slate-800 via-slate-850 to-slate-900`
- **Text Color**: White
- **Shadow**: `shadow-xl`

#### Sidebar Sections
1. **Logo Section**: `p-5 border-b border-slate-700/50`
2. **Navigation**: `flex-1 p-4 space-y-1`
3. **Bottom Section**: `p-4 border-t border-slate-700/50`

#### Navigation Links
- **Class**: `flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium`
- **Active State**: `bg-gradient-to-r from-primary-500/20 to-primary-600/10 text-primary-400 border border-primary-500/30`
- **Inactive State**: `text-slate-300 hover:bg-slate-700/50 hover:text-white`

#### Section Headers
- **Class**: `px-4 text-xs font-semibold text-slate-500 uppercase tracking-wider`

### Header Design
- **Background**: `bg-white/80 backdrop-blur-sm`
- **Border**: `border-b border-slate-200`
- **Padding**: `px-4 py-2`
- **Layout**: `flex items-center justify-between`

#### Page Title
- **Title**: `text-xl font-semibold text-slate-800`
- **Subtitle**: `text-sm text-slate-500`

### Main Content Area
- **Padding**: `p-2`
- **Overflow**: `overflow-auto`
- **Flex**: `flex-1`

### Footer Design
- **Background**: `bg-white/50`
- **Border**: `border-t border-slate-200`
- **Padding**: `px-4 py-2`
- **Text**: `text-center text-sm text-slate-500`

---

## Component Patterns

### 1. Cards

#### Standard Card
```html
<div class="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
    <div class="px-6 py-4 border-b border-slate-200 bg-gradient-to-r from-slate-50 to-white">
        <h2 class="text-lg font-semibold text-slate-800">Card Title</h2>
    </div>
    <div class="p-6">
        <!-- Content -->
    </div>
</div>
```

#### Compact Card (for forms)
```html
<div class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
    <div class="px-4 py-2 border-b border-slate-200 bg-gradient-to-r from-slate-50 to-white">
        <h2 class="text-lg font-semibold text-slate-800">Section Title</h2>
    </div>
    <div class="p-3 space-y-2">
        <!-- Content -->
    </div>
</div>
```

#### Stats Card
```html
<div class="bg-white rounded-2xl shadow-sm border border-slate-200 p-2 hover:shadow-md transition-shadow">
    <div class="flex items-center gap-1">
        <div class="w-12 h-12 bg-gradient-to-br from-primary-500 to-primary-600 rounded-xl flex items-center justify-center">
            <svg class="w-6 h-6 text-white">...</svg>
        </div>
        <div>
            <p class="text-xl font-bold text-slate-800">Value</p>
            <p class="text-xs text-slate-500">Label</p>
        </div>
    </div>
</div>
```

### 2. Buttons

#### Primary Button
```html
<button class="px-6 py-3 bg-gradient-to-r from-primary-500 to-primary-600 text-white font-semibold rounded-xl hover:from-primary-600 hover:to-primary-700 shadow-md hover:shadow-lg transition-all flex items-center gap-2">
    <svg class="w-5 h-5">...</svg>
    Button Text
</button>
```

#### Success Button
```html
<button class="px-4 py-2.5 bg-gradient-to-r from-emerald-500 to-emerald-600 text-white font-medium rounded-xl hover:from-emerald-600 hover:to-emerald-700 shadow-sm transition-all flex items-center gap-2">
    <svg class="w-5 h-5">...</svg>
    Action
</button>
```

#### Danger Button
```html
<button class="px-5 py-2.5 text-sm font-medium text-white bg-gradient-to-r from-red-500 to-red-600 hover:from-red-600 hover:to-red-700 rounded-xl shadow-sm transition-all">
    Delete
</button>
```

#### Secondary Button
```html
<button class="px-6 py-3 bg-white border border-slate-300 text-slate-700 font-medium rounded-xl hover:bg-slate-50 transition-colors">
    Cancel
</button>
```

#### Neutral Button
```html
<button class="px-5 py-2.5 text-sm font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-xl transition-colors">
    Cancel
</button>
```

#### Icon Button (Action)
```html
<button class="p-2 text-slate-400 hover:text-primary-600 hover:bg-primary-50 rounded-lg transition-colors">
    <svg class="w-4 h-4">...</svg>
</button>
```

### 3. Form Elements

#### Text Input
```html
<div>
    <label for="field" class="block text-sm font-medium text-slate-700 mb-1">
        Field Label <span class="text-red-500">*</span>
    </label>
    <input type="text" name="field" id="field" required
           class="w-full px-2 py-2 rounded-xl border border-slate-300 focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-shadow"
           placeholder="Enter value">
</div>
```

#### Number Input
```html
<input type="number" name="field" min="0" step="0.1"
       class="w-full px-3 py-2 rounded-xl border border-slate-300 focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-shadow">
```

#### Select Dropdown
```html
<select name="field" required
        class="w-full px-4 py-2.5 rounded-xl border border-slate-300 focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-shadow bg-white">
    <option value="">Select...</option>
    <option value="1">Option 1</option>
</select>
```

#### Textarea
```html
<textarea name="field" rows="2"
          class="w-full px-2 py-2 rounded-xl border border-slate-300 focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-shadow resize-none"
          placeholder="Enter text..."></textarea>
```

#### Checkbox
```html
<div class="flex items-center gap-2 py-2">
    <input type="checkbox" name="field" id="field"
           class="w-5 h-5 rounded border-slate-300 text-primary-600 focus:ring-primary-500">
    <label for="field" class="text-sm font-medium text-slate-700">Checkbox Label</label>
</div>
```

#### Date Input
```html
<input type="date" name="date" required
       class="w-full px-2 py-2 rounded-xl border border-slate-300 focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-shadow">
```

### 4. Tables

#### Reusable Table Component

Use the reusable table component from `components/scrollable_table.html`:

```jinja2
{% from 'components/scrollable_table.html' import table_card, table_header_classes, empty_state %}

{% call table_card(title="Table Title", count_label=items|length ~ " items") %}
<table class="w-full">
    <thead class="{{ table_header_classes() }}">
        <tr class="bg-slate-50 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">
            <th class="px-6 py-2">Column Name</th>
        </tr>
    </thead>
    <tbody class="divide-y divide-slate-100">
        {% for item in items %}
        <tr class="table-row-hover">
            <td class="px-6 py-2 text-sm text-slate-700">{{ item.value }}</td>
        </tr>
        {% else %}
        {{ empty_state(col_count=1, title="No data", message="Add your first item.") }}
        {% endfor %}
    </tbody>
</table>
{% endcall %}
```

**Component Macros:**
- `table_card(title, count_label, full_height)` - Card wrapper with optional header
- `table_header_classes(full_height)` - Returns sticky header classes when `full_height=true`
- `empty_state(col_count, icon_path, title, message)` - Empty table state row

#### Viewport-Filling Scrollable Table (Dashboard)
```html
<div class="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden flex-1 flex flex-col">
    <div class="overflow-x-auto overflow-y-auto flex-1">
        <table class="w-full">
            <thead class="sticky top-0 z-10 bg-slate-50">
                <!-- Headers -->
            </thead>
            <tbody class="divide-y divide-slate-100">
                <!-- Rows -->
            </tbody>
        </table>
    </div>
</div>
```

#### Table Container (Standard)
```html
<div class="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
    <div class="px-4 py-2 border-b border-slate-200 bg-gradient-to-r from-slate-50 to-white flex items-center justify-between">
        <h2 class="text-lg font-semibold text-slate-800">Table Title</h2>
        <span class="px-3 py-1 bg-slate-100 text-slate-600 rounded-full text-sm font-medium">5 items</span>
    </div>
    <div class="overflow-x-auto">
        <table class="w-full">...</table>
    </div>
</div>
```

#### Table Header (Compact)
```html
<thead class="bg-slate-50">
    <tr class="bg-slate-50 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">
        <th class="px-6 py-2">Column Name</th>
    </tr>
</thead>
```

#### Table Header with Sorting
```html
<th class="px-2 py-2 align-top">
    <a href="?sort=field&order=desc" 
       class="flex items-center gap-1 hover:text-primary-600">
        Column Name
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
        </svg>
    </a>
</th>
```

#### Table Body (Compact)
```html
<tbody class="divide-y divide-slate-100">
    <tr class="table-row-hover">
        <td class="px-6 py-2 text-sm text-slate-700">Cell content</td>
    </tr>
</tbody>
```

#### Table Row Hover Effect
```css
.table-row-hover:hover {
    background-color: #f8fafc;
}
```

#### Empty State
```html
<tr>
    <td colspan="5" class="px-6 py-12 text-center text-slate-500">
        <svg class="w-12 h-12 mx-auto mb-4 text-slate-300">...</svg>
        <p class="text-lg font-medium">No Records</p>
        <p class="text-sm">Add your first record using the form above.</p>
    </td>
</tr>
```

### 5. Badges

#### Standard Badge
```html
<span class="px-3 py-0.5 bg-slate-100 text-slate-700 rounded font-mono text-xs">
    Value
</span>
```

#### Primary Badge
```html
<span class="px-3 py-1 bg-primary-100 text-primary-700 rounded-lg text-sm font-medium">
    Value
</span>
```

#### Success Badge
```html
<span class="inline-flex items-center align-text-top px-2 py-0.5 rounded text-xs font-normal bg-emerald-100 text-emerald-700">
    Success
</span>
```

#### Warning Badge
```html
<span class="px-2 py-1 bg-amber-100 text-amber-700 rounded-lg text-sm font-medium">
    Warning
</span>
```

#### Count Badge
```html
<span class="px-3 py-1 bg-slate-100 text-slate-600 rounded-full text-sm font-medium">
    24 items
</span>
```

### 6. Flash Messages

#### Flash Message Component
```html
<div class="px-6 pt-4 space-y-2">
    <div class="flex items-center gap-3 px-4 py-3 rounded-xl shadow-sm
                bg-gradient-to-r from-emerald-50 to-green-50 border border-emerald-200 text-emerald-800">
        <svg class="w-5 h-5 text-emerald-500 flex-shrink-0">...</svg>
        <p class="text-sm font-medium flex-1">Success message</p>
        <button onclick="this.parentElement.remove()" class="p-1 rounded-lg hover:bg-white/50">
            <svg class="w-4 h-4 opacity-60">...</svg>
        </button>
    </div>
</div>
```

#### Message Types
- **Success**: `from-emerald-50 to-green-50 border-emerald-200 text-emerald-800`
- **Error**: `from-red-50 to-rose-50 border-red-200 text-red-800`
- **Warning**: `from-amber-50 to-yellow-50 border-amber-200 text-amber-800`
- **Info**: `from-blue-50 to-indigo-50 border-blue-200 text-blue-800`

### 7. Modals

#### Modal Structure
```html
<div id="modal" class="fixed inset-0 z-50 hidden">
    <!-- Backdrop -->
    <div class="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" onclick="closeModal()"></div>
    
    <!-- Modal -->
    <div class="absolute inset-0 flex items-center justify-center p-4">
        <div class="relative bg-white rounded-2xl shadow-2xl max-w-md w-full transform transition-all">
            <!-- Header -->
            <div class="px-6 pt-6 pb-4">
                <div class="flex items-center gap-4">
                    <div class="w-12 h-12 rounded-xl flex items-center justify-center bg-red-100">
                        <svg class="w-6 h-6 text-red-600">...</svg>
                    </div>
                    <div>
                        <h3 class="text-lg font-semibold text-slate-800">Modal Title</h3>
                        <p class="text-sm text-slate-500">Modal message</p>
                    </div>
                </div>
            </div>
            
            <!-- Actions -->
            <div class="px-6 pb-6 pt-2 flex items-center justify-end gap-3">
                <button class="px-5 py-2.5 text-sm font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-xl">
                    Cancel
                </button>
                <button class="px-5 py-2.5 text-sm font-medium text-white bg-gradient-to-r from-red-500 to-red-600 hover:from-red-600 hover:to-red-700 rounded-xl shadow-sm">
                    Confirm
                </button>
            </div>
        </div>
    </div>
</div>
```

### 8. Filter Pills / Tabs

#### Filter Pills
```html
<div class="flex flex-wrap gap-2">
    <a href="?filter=active" 
       class="px-3 py-1.5 text-sm rounded-lg transition-colors bg-primary-500 text-white">
        Active Filter
    </a>
    <a href="?filter=inactive" 
       class="px-3 py-1.5 text-sm rounded-lg transition-colors bg-slate-100 text-slate-600 hover:bg-slate-200">
        Inactive Filter
    </a>
</div>
```

---

## Spacing & Layout

### Spacing Scale
- **Compact spacing**: `gap-1`, `space-y-1`, `p-1`
- **Default spacing**: `gap-2`, `space-y-2`, `p-2`
- **Comfortable spacing**: `gap-3`, `space-y-3`, `p-3` (preferred for page layouts)
- **Spacious**: `gap-4`, `space-y-4`, `p-4`
- **Extra spacious**: `gap-6`, `space-y-6`, `p-6`

### Page Content Spacing
- **Card stacks**: `space-y-3` (preferred for form + table layouts)
- **Form grids**: `gap-2` for form field grids

### Card Padding
- **Header**: `px-6 py-2` (compact/preferred) or `px-6 py-4` (standard)
- **Body**: `p-6` (standard) or `p-3` (compact)
- **Table card header**: `px-4 py-2` with count badge

### Table Cell Padding
- **Header cells**: `px-6 py-2`
- **Body cells**: `px-6 py-2` (compact/preferred) or `px-6 py-4` (spacious)

### Grid Layouts
- **Two columns**: `grid grid-cols-1 md:grid-cols-2 gap-2`
- **Four columns**: `grid grid-cols-1 md:grid-cols-4 gap-2`
- **Six columns (stats)**: `grid grid-cols-1 md:grid-cols-6 gap-1`

---

## Border Radius

### Standard Radii
- **Small**: `rounded-lg` (8px)
- **Medium**: `rounded-xl` (12px)
- **Large**: `rounded-2xl` (16px)
- **Full**: `rounded-full` (9999px)

### Component-Specific
- **Cards**: `rounded-2xl` (standard) or `rounded-xl` (compact)
- **Buttons**: `rounded-xl`
- **Inputs**: `rounded-xl`
- **Badges**: `rounded` or `rounded-lg`
- **Icons containers**: `rounded-xl`

---

## Shadows

### Shadow Scale
- **Subtle**: `shadow-sm`
- **Standard**: `shadow-md`
- **Elevated**: `shadow-lg`
- **Extra elevated**: `shadow-xl`
- **Modal**: `shadow-2xl`

### Interactive Shadows
- **Button hover**: `shadow-md hover:shadow-lg`
- **Card hover**: `shadow-sm hover:shadow-md`

---

## Transitions & Animations

### Global Transitions
```css
* {
    transition-property: background-color, border-color, color, fill, stroke, opacity, box-shadow, transform;
    transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
    transition-duration: 300ms;
}
```

### Common Transition Classes
- **All properties**: `transition-all`
- **Colors**: `transition-colors`
- **Shadows**: `transition-shadow`

---

## Custom Scrollbar

```css
::-webkit-scrollbar {
    width: 8px;
    height: 8px;
}
::-webkit-scrollbar-track {
    background: #f1f5f9;
}
::-webkit-scrollbar-thumb {
    background: #cbd5e1;
    border-radius: 4px;
}
::-webkit-scrollbar-thumb:hover {
    background: #94a3b8;
}
```

---

## Interactive Features

### 1. Table Sorting

#### Frontend Pattern
```html
<a href="{{ url_for('route', sort='field', order='asc' if order == 'desc' else 'desc') }}" 
   class="flex items-center gap-1 hover:text-primary-600">
    Column Name
    {% if sort_by == 'field' %}
    <svg class="w-4 h-4 {{ 'rotate-180' if order == 'asc' else '' }}">
        <!-- Down arrow icon -->
    </svg>
    {% endif %}
</a>
```

### 2. Real-time Search

#### Search Input in Table Header
```html
<input type="text" id="search_field" placeholder="Szukaj..." 
       class="w-full px-1 py-0.5 text-xs font-normal normal-case rounded border border-slate-300 focus:ring-1 focus:ring-primary-500 focus:border-primary-500">
```

#### JavaScript Pattern (Debounced)
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

const debouncedSearch = debounce(() => applyFilters('search_field'), 500);

document.getElementById('search_field').addEventListener('keyup', function(e) {
    if (e.key === 'Enter') {
        applyFilters('search_field');
    } else {
        debouncedSearch();
    }
});
```

### 3. Confirmation Modal

#### JavaScript Pattern
```javascript
function confirmDelete(form, itemName) {
    showConfirmModal(
        form,
        'Potwierdź usunięcie',
        `Czy na pewno chcesz usunąć "${itemName}"? Ta operacja jest nieodwracalna.`,
        'Usuń'
    );
    return false; // Prevent form submission
}
```

#### Form Integration
```html
<form onsubmit="return confirmDelete(this, 'Item Name');">
    <button type="submit">Delete</button>
</form>
```

---

## Icon Usage

### Icon Library
Use **Heroicons** (inline SVG, 24x24 viewBox)

### Standard Icon Sizes
- **Extra small**: `w-4 h-4` (16px) - preferred for table action buttons
- **Small**: `w-5 h-5` (20px) - for buttons with text
- **Medium**: `w-6 h-6` (24px) - for stats cards, navigation
- **Large**: `w-8 h-8` (32px) - for category icons in tables
- **Extra Large**: `w-12 h-12` (48px) - for empty states

### Icon Colors
- **Default**: `text-slate-400` (inactive actions)
- **Hover states**: 
  - View: `hover:text-emerald-600`
  - Edit: `hover:text-primary-600`
  - Delete: `hover:text-red-600`
- **In buttons**: `text-white`
- **In colored badges**: Match badge color (e.g., `text-emerald-500`)

---

## Responsive Design

### Breakpoints
- **Mobile**: Default (no prefix)
- **Tablet**: `md:` (768px+)
- **Desktop**: `lg:` (1024px+)

### Common Responsive Patterns
```html
<!-- Stacked on mobile, 2 columns on tablet -->
<div class="grid grid-cols-1 md:grid-cols-2 gap-2">

<!-- Stacked on mobile, 4 columns on tablet -->
<div class="grid grid-cols-1 md:grid-cols-4 gap-4">

<!-- Full width on mobile, fixed width on desktop -->
<div class="w-full md:w-64">

<!-- Hide on mobile, show on desktop -->
<div class="hidden md:block">
```

---

## Best Practices

### 1. Consistency
- Always use `rounded-xl` for inputs, buttons, and small cards
- Always use `rounded-2xl` for larger cards and containers
- Maintain consistent spacing (`p-6` for standard cards, `p-3` for compact)

### 2. Accessibility
- Always include `<label>` elements for form inputs
- Use semantic HTML (`<header>`, `<main>`, `<footer>`, `<nav>`)
- Include ARIA labels where appropriate
- Ensure sufficient color contrast

### 3. Performance
- Use Tailwind's CDN for rapid development
- Minimize custom CSS (use Tailwind utilities)
- Lazy-load heavy content where appropriate

### 4. User Experience
- Provide visual feedback for all interactions (hover states, focus rings)
- Use loading states for async operations
- Include empty states with helpful messages
- Always show confirmation for destructive actions

### 5. Typography
- Use `font-semibold` or `font-bold` for headings
- Use `text-sm` or `text-xs` for secondary text
- Use `font-medium` for emphasized text in tables/lists

---

## Template Structure

### Base Template (base.html)
```jinja2
<!DOCTYPE html>
<html lang="pl" class="h-full">
<head>
    <title>{% block title %}App Name{% endblock %}</title>
    <!-- Fonts, Tailwind, Custom Styles -->
</head>
<body class="h-full bg-gradient-to-br from-slate-50 to-slate-100 font-sans antialiased">
    <div class="flex h-full">
        {% include 'components/sidebar.html' %}
        
        <div class="flex-1 flex flex-col min-h-screen overflow-hidden">
            <header>
                <h1>{% block page_title %}{% endblock %}</h1>
                <p>{% block page_subtitle %}{% endblock %}</p>
            </header>
            
            {% include 'components/flash_messages.html' %}
            
            <main class="flex-1 overflow-auto p-2">
                {% block content %}{% endblock %}
            </main>
            
            <footer>...</footer>
        </div>
    </div>
    
    {% include 'components/confirm_modal.html' %}
    {% block scripts %}{% endblock %}
</body>
</html>
```

### Page Template
```jinja2
{% extends 'base.html' %}

{% block title %}Page Title{% endblock %}
{% block page_title %}Page Heading{% endblock %}
{% block page_subtitle %}Page Description{% endblock %}

{% block content %}
<!-- Page content here -->
{% endblock %}

{% block scripts %}
<!-- Page-specific JavaScript -->
{% endblock %}
```

---

## Component Files

### Reusable Components Directory
Create components in `app/templates/components/`:
- `sidebar.html` - Navigation sidebar
- `flash_messages.html` - Alert notifications
- `confirm_modal.html` - Confirmation dialog
- `scrollable_table.html` - Reusable table macros

### Component Inclusion
```jinja2
{# For includes #}
{% include 'components/sidebar.html' %}

{# For macro imports #}
{% from 'components/scrollable_table.html' import table_card, empty_state %}
```

---

## Form Design Patterns

### Multi-Section Form
```html
<form method="POST" class="max-w-4xl space-y-3">
    <!-- Section 1 -->
    <div class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div class="px-4 py-2 border-b border-slate-200 bg-gradient-to-r from-slate-50 to-white">
            <h2 class="text-lg font-semibold text-slate-800">Section Title</h2>
        </div>
        <div class="p-3 space-y-2">
            <!-- Form fields -->
        </div>
    </div>
    
    <!-- Section 2 -->
    <div class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <!-- ... -->
    </div>
    
    <!-- Actions -->
    <div class="flex items-center gap-2">
        <button type="submit" class="px-6 py-3 bg-gradient-to-r from-primary-500 to-primary-600 text-white font-semibold rounded-xl hover:from-primary-600 hover:to-primary-700 shadow-md hover:shadow-lg transition-all">
            Save
        </button>
        <a href="/" class="px-6 py-3 bg-white border border-slate-300 text-slate-700 font-medium rounded-xl hover:bg-slate-50 transition-colors">
            Cancel
        </a>
    </div>
</form>
```

---

## Summary Checklist

When creating a new Flask/Jinja2 project, ensure:

- ✅ Use Inter font from Google Fonts
- ✅ Configure Tailwind CSS with custom primary/accent colors
- ✅ Implement sidebar with gradient background and active states
- ✅ Use consistent card styling (rounded-2xl, shadow-sm, border)
- ✅ Apply consistent button gradients (primary, success, danger)
- ✅ Use rounded-xl for all inputs with focus rings
- ✅ Implement flash messages with color-coded categories
- ✅ Include confirmation modal for destructive actions
- ✅ Add table sorting and real-time search when applicable
- ✅ Use semantic colors (emerald for success, red for errors, etc.)
- ✅ Add hover states to all interactive elements
- ✅ Include empty states with helpful icons and messages
- ✅ Use custom scrollbar styling
- ✅ Apply global transitions for smooth interactions
- ✅ Follow responsive design patterns (mobile-first)

---

## Version

**Version**: 2.1  
**Framework**: Flask + Tailwind CSS  
**Last Updated**: 2026-01-23  
**Changes**: Added reusable table component, compact spacing standards, updated icon sizes
