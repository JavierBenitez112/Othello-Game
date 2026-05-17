# UI

This directory contains small reusable UI primitives used across the admin dashboard.

## What is here

- `button.tsx`
- `input.tsx`
- `label.tsx`
- `badge.tsx`
- `card.tsx`
- `table.tsx`
- `alert.tsx`

These files are lightweight presentation components, not business logic.

## Dependencies

- React
- Tailwind CSS
- utility helpers such as `cn` from `../../lib/utils`
- Radix UI for some accessible primitives

## How to use

Import these components into higher-level files in `../` or page files in `../../app`.

Example:

```tsx
import { Button } from "@/components/ui/button";
```

## When to edit these files

Edit this directory when you want to change:

- shared styling
- common interaction patterns
- base accessibility behavior

Do not put API calls or tournament logic here.
