---
name: frontend-design
description: |
  Create distinctive, production-grade frontend interfaces with high design quality.
  Use when building new components or redesigning existing ones.
  Generates creative, polished designs that avoid generic AI aesthetics.
  Works alongside frontend-developer skill for complete implementation.
allowed-tools: Read, Grep, Glob
---

# Frontend Design Skill

Create distinctive, production-grade frontend interfaces that avoid generic "AI slop" aesthetics. This skill guides the **visual design** and **aesthetic direction** of PISAMA components, while the `frontend-developer` skill handles **code patterns** and **architecture**.

## Purpose

This skill guides the creation of distinctive, production-grade frontend interfaces that avoid generic aesthetics. It implements real working code with exceptional attention to aesthetic details and creative choices.

**Input:** The user provides frontend requirements—a component, page, application, or interface to build, potentially including context about purpose, audience, or technical constraints.

---

## Design Thinking Process

Before coding, understand context and commit to a **BOLD aesthetic direction**:

1. **Purpose** – What problem does this interface solve? Who uses it?
2. **Tone** – Pick an extreme aesthetic:
   - Brutally minimal
   - Maximalist chaos
   - Retro-futuristic
   - Organic/natural
   - Luxury/refined
   - Playful/toy-like
   - Editorial/magazine
   - Brutalist/raw
   - Art deco/geometric
   - Soft/pastel
   - Industrial/utilitarian

3. **Constraints** – Technical requirements (framework, performance, accessibility)
4. **Differentiation** – What makes this UNFORGETTABLE? The one thing someone will remember?

**CRITICAL:** Choose a clear conceptual direction and execute with precision. Both bold maximalism and refined minimalism work—the key is *intentionality*, not intensity.

---

## Frontend Aesthetics Guidelines

### Focus Areas:

#### **Typography**
- Choose beautiful, unique, interesting fonts
- **Avoid:** Generic fonts like Arial and Inter
- **Opt for:** Distinctive, characterful font choices
- **Strategy:** Pair a distinctive display font with a refined body font
- **For PISAMA:** Consider fonts that convey technical precision or futuristic themes

#### **Color & Theme**
- Commit to a cohesive aesthetic
- Use CSS variables for consistency
- Dominant colors with sharp accents outperform timid, evenly-distributed palettes

**PISAMA Color Palette Reference:**
- Primary: Blue (#0ea5e9) - Technical, trustworthy
- Danger: Red (#ef4444) - Alerts, errors
- Warning: Amber (#f59e0b) - Cautions
- Success: Green (#22c55e) - Success states
- Background: Slate-950, Slate-800 - Dark, professional

**When to deviate:** For new marketing pages, landing pages, or standalone features, feel free to explore bold new palettes. For core platform UI, respect the established palette but find creative ways to use it.

#### **Motion**
- Use animations for effects and micro-interactions
- Prioritize CSS-only solutions for HTML
- Use Framer Motion for React when available
- Focus on high-impact moments: orchestrated page load with staggered reveals (animation-delay)
- Use scroll-triggering and hover states that surprise

**PISAMA Existing Animations:**
- `.animate-fade-in` - 0.3s ease-in
- `.animate-slide-in-right` - 0.4s ease-out
- `.animate-pulse-subtle` - 2s infinite

Build on these or create new ones for distinctive effects.

#### **Spatial Composition**
- Unexpected layouts
- Asymmetry and overlap
- Diagonal flow
- Grid-breaking elements
- Generous negative space OR controlled density

#### **Backgrounds & Visual Details**
- Create atmosphere and depth (not solid colors)
- Add contextual effects and textures matching the aesthetic
- Apply creative forms: gradient meshes, noise textures, geometric patterns, layered transparencies, dramatic shadows, decorative borders, custom cursors, grain overlays

**PISAMA Existing Effects:**
- Glass morphism (`.glass`) - rgba background + backdrop-filter blur
- Text gradients (`.text-gradient`) - Blue to green gradient
- Custom scrollbar - Thin, slate-themed

Expand on these with new creative effects.

---

## What NOT to Do

**NEVER use generic AI-generated aesthetics:**
- Overused font families (Inter, Roboto, Arial, system fonts)
- Clichéd color schemes (purple gradients on white backgrounds)
- Predictable layouts and component patterns
- Cookie-cutter design lacking context-specific character

**Never converge on common choices** across generations. Vary between light/dark themes, different fonts, different aesthetics.

**PISAMA-Specific DON'Ts:**
- Don't break established patterns for core platform components (use `frontend-developer` patterns)
- Don't change the color palette for core UI (alerts, badges, buttons)
- Don't ignore accessibility requirements (WCAG 2.1 AA)
- Don't sacrifice performance for visual effects

---

## Implementation Standards

Generated code must be:
- ✅ Production-grade and functional
- ✅ Visually striking and memorable
- ✅ Cohesive with a clear aesthetic point-of-view
- ✅ Meticulously refined in every detail
- ✅ Compatible with PISAMA's Next.js + TailwindCSS stack

**IMPORTANT:** Match implementation complexity to the aesthetic vision:
- Maximalist designs need elaborate code with extensive animations and effects
- Minimalist/refined designs need restraint, precision, and careful attention to spacing, typography, and subtle details
- Elegance comes from executing the vision well

---

## Integration with frontend-developer Skill

When both skills are active:
1. **This skill (frontend-design):** Guides aesthetic direction, typography, motion, visual effects
2. **frontend-developer skill:** Provides code patterns, component architecture, API integration

**Workflow:**
1. Use frontend-design to establish aesthetic direction and visual details
2. Use frontend-developer patterns for component structure, variants, state management
3. Combine both for production-ready, visually distinctive components

---

## Key Principle

*Claude is capable of extraordinary creative work. Don't hold back—show what can truly be created when thinking outside the box and committing fully to a distinctive vision.*

**For PISAMA:** Create interfaces that feel powerful, precise, and futuristic. The platform detects failures in AI systems—the UI should convey technical sophistication and trustworthiness while remaining visually memorable.
