## OpenPencil Usage Guidelines

When the user wants to inspect, search, or export a `.fig` (Figma) design file, use the OpenPencil CLI tools.

**Key principles:**
- Use `openpencil_info` to get document stats first — node count, fonts used, frame names — before diving deeper
- Use `openpencil_tree` to visualize the layer hierarchy of a design file
- Use `openpencil_find` to search for nodes by name or type (e.g., find all "Button" components)
- Use `openpencil_export` to render frames or components to PNG or JPG

**When to use OpenPencil:**
- User uploads or references a `.fig` file and wants to know what's in it
- User wants to extract assets or screenshots from a Figma design
- User wants to audit a design file (fonts, components, structure)
- User wants to automate design asset export in a CI/CD pipeline

**File path handling:**
- The `file` parameter always takes an absolute path to the `.fig` file on disk
- If the user provides a relative path, resolve it from their home directory or current working directory
- If the file doesn't exist, report the error clearly and ask the user to provide the correct path

**Output format:**
- All tools support a `json` parameter (boolean) — set to `true` when you need structured data for further processing
- Default output is human-readable; use JSON when piping results to other tools

**Export tips:**
- Default format is PNG; use `format: "jpg"` for smaller files with quality loss acceptable
- Use `scale: 2` for Retina/high-DPI exports
- `node_id` is optional — if omitted, exports all top-level frames
