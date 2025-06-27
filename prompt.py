"""
Property analysis prompts for GPT-4V with structured output format
"""

PROPERTY_ANALYSIS_PROMPT = """# GPT-4V Property Photo Analysis for Rental Market Assessment

You are analyzing rental property **interior and exterior photos** for objective market evaluation. Use ONLY what is **clearly and visibly shown** in the images. Do not guess or assume any features that are not fully and visibly present.

You will output a structured scoring summary, following strict inclusion criteria for each scoring category.

---

## 🔢 IMAGE REFERENCING

- Images are labeled as **Image 1, Image 2, Image 3, …** in the order they are uploaded or presented.
- You must explicitly reference image numbers used for each scoring category.
- Do NOT infer content from unlabeled images. Only use numbered images.
- If no image clearly qualifies for a category, write **“None visible”** — do not guess or assume.

---

## 🚫 CRITICAL INSTRUCTIONS

1. **Only score what is clearly visible** — no assumptions based on style, staging, or context clues.
2. **Use a conservative approach** — when in doubt, do NOT include the image or choose the lower score tier.
3. **Do not reuse images** across categories unless they meet both categories' criteria fully.
4. **Follow scoring category checklists strictly** (see below).
5. **Use the exact structured output format provided at the end**.

---

## 📊 SCORING RUBRICS (Each scored on a 1–10 scale)

Evaluate **each scoring category independently**, only using valid images for that category.

### 🔪 KITCHEN QUALITY (1–10)

#### ✅ A valid image MUST show ALL:
- At least one cooking appliance (stove, oven, microwave, cooktop, etc.)
- Kitchen countertop or food prep area
- Cabinetry, island, or sink for food prep or cleaning

#### ❌ DO NOT use:
- Dining areas, living rooms, or rooms without clear kitchen elements
- Images missing appliances or showing only part of a kitchen

**Scoring Tiers:**
- **1–2 (Poor):** Broken/missing appliances, severe damage
- **3–4:** Very small (<60 sq ft), worn or dated appliances/surfaces
- **5–6:** Functional small–medium kitchen with standard features
- **7–8:** Modern, medium–large with quality appliances/finishes
- **9–10:** High-end, large, luxury design, premium finishes

---

### 🚿 BATHROOM QUALITY (1–10)

#### ✅ A valid image MUST show ANY of the following:
- Toilet, sink, shower, or bathtub clearly visible
- Bathroom-specific vanities, fixtures, or tiling

#### ❌ DO NOT use:
- Laundry rooms, partial sinks, closeups, or non-bathroom areas

**Scoring Tiers:**
- **1–2:** Broken/unsafe fixtures
- **3–4:** Cramped, basic, dated but functional
- **5–6:** Clean, standard fixtures, adequate space
- **7–8:** Premium materials or spacious layout
- **9–10:** Spa-like space with luxury finishes

---

### 🌞 NATURAL LIGHT (1–10)

#### ✅ A valid image MUST show:
- **Interior unit space** (living room, bedroom, or kitchen)
- Visible windows with **daylight coming through**

#### ❌ DO NOT use:
- Outdoor scenes, night shots, views without interior space, rooms with no windows or visible sunlight

**Scoring Tiers:**
- **1–2:** Very dark, minimal windows
- **3–4:** Limited lighting/windows
- **5–6:** Decent natural light
- **7–8:** Bright space, multiple windows
- **9–10:** Floor-to-ceiling windows, abundant light

---

### 🛠️ OVERALL CONDITION (1–10)

#### ✅ A valid image MUST show:
- Interior unit surfaces (walls, floors, ceilings, finishes)
- Fixtures, hardware, or materials showing wear or cleanliness

#### ❌ DO NOT use:
- Building exteriors, blurry or low-resolution photos, outdoor views

**Scoring Tiers:**
- **1–2:** Major damage or visible disrepair
- **3–4:** Minor visible wear, scuffing, chips
- **5–6:** Normal wear and tear, well-kept
- **7–8:** Excellent maintenance, updated
- **9–10:** Like new, pristine, recently renovated

---

### 🛋️ LIVING SPACE QUALITY (1–10)

#### ✅ A valid image MUST show:
- **Interior living areas**: living room, bedroom, or dining room
- Clear flooring, ceiling height, layout, or furniture arrangement

#### ❌ DO NOT use:
- Kitchens, bathrooms, hallways, or exteriors

**Scoring Tiers:**
- **1–2:** Severely damaged or cramped
- **3–4:** Worn or awkward layout, low ceilings
- **5–6:** Standard quality
- **7–8:** High ceilings, good flooring/layout
- **9–10:** Premium design, great proportions

---

### 📏 SIZE / SPACE (1–10)

#### ✅ A valid image MUST show:
- Full room or multiple-room views with visible scale
- Ceiling height and spatial layout visible with reference objects

#### ❌ DO NOT use:
- Closeups, partial views, floorplans, outdoor images

**Scoring Tiers:**
- **1–2:** Extremely small/cramped
- **3–4:** Compact but functional
- **5–6:** Standard room sizes
- **7–8:** Spacious with good ceiling height
- **9–10:** Expansive, luxurious proportions

---

### 🏢 BUILDING QUALITY (1–10)

#### ✅ A valid image MUST show:
- Exterior building façade, lobby, hallway, or shared amenity
- Neighborhood views or visible building materials

#### ❌ DO NOT use:
- Interior unit rooms, bedrooms, kitchens, bathrooms

**Scoring Tiers:**
- **1–2:** Poor condition, visibly old or unsafe
- **3–4:** Dated building, limited amenities
- **5–6:** Modern with basic amenities (gym, laundry)
- **7–8:** High-end materials, amenities, lobby
- **9–10:** Luxury building, concierge, rooftop, pool, spa

---

## 📦 PROPERTY DETAILS (Visually Assessed)
These should be visually determined unless clearly not visible:

- **Property Type:** [Studio / 1BR / 2BR / 3BR+ / House / Unknown]
- **Furnishing Status:** [Fully Furnished / Partially Furnished / Unfurnished / Unknown]
- **Digital Staging Present:** [Yes / No / Unknown]
- **Outdoor Space Visible:** [Yes / No]
- **Estimated Square Footage (visual estimate):** [X] sq ft

---

## 🧾 AMENITIES OBSERVED
List clearly visible items such as:

- **Appliances**: dishwasher, stainless appliances
- **Finishes**: granite countertops, hardwood floors
- **Outdoor features**: balcony, terrace, patio, yard
- **Building features**: rooftop access, gym, doorman, pool, parking, laundry

If none are clearly visible, write:  
→ **None clearly visible**

---

## ✏️ STRUCTURED OUTPUT FORMAT

Copy and fill in:

---

**PROPERTY SCORING ANALYSIS**

**CORE QUALITY SCORES:**  
Kitchen Quality: [X]/10 – [thorough justification include specific matierials / appliances ]  
Bathroom Quality: [X]/10 – [thorough justification include specifics]  
Natural Light: [X]/10 – [thorough justification]  
Overall Condition: [X]/10 – [thorough justification]  
Living Space Quality: [X]/10 – [thorough justification]  
Size/Space Score: [X]/10 – [thorough justification]  
Building Quality: [X]/10 – [thorough justification]

**PROPERTY DETAILS:**  
Property Type: [Studio/1BR/2BR/3BR+/House/Unknown]  
Furnishing Status: [Fully Furnished/Partially Furnished/Unfurnished/Unknown]  
Digital Staging: [Yes/No/Unknown]  
Outdoor Space: [Yes/No]  
Estimated Square Footage: [X] sq ft

**AMENITIES OBSERVED:**  
[List as comma-separated values or “None clearly visible”]

**ASSESSMENT NOTES:**  
Total Images Analyzed: [X]  
Areas Unable to Assess: [e.g., “Kitchen,” “Building quality,” or “None”]  
Scoring Confidence: [High/Medium/Low]

**IMAGE ANALYSIS BREAKDOWN:**  
Images used for Kitchen scoring: [e.g., 1, 4]  
Images used for Bathroom scoring: [e.g., 2, 5]  
Images used for Natural Light scoring: [e.g., 1, 6]  
Images used for Living Space scoring: [e.g., 3, 6]  
Images used for Building/Exterior scoring: [e.g., 7, 8]  
Images used for Size/Space scoring: [e.g., 1, 2, 3]

**CONSISTENCY VERIFICATION:**  
All scores based only on clearly visible features: [Yes/No]  
Conservative approach used when visual information limited: [Yes/No]  
Image categorization follows strict rules above: [Yes/No]

---

"""