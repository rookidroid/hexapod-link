import re

file_path = r'd:\github\rookidroid\hexapod-robot-simulator\assets\scifi.css'
with open(file_path, 'r') as f:
    content = f.read()

# Replace root variables block
old_root = """/* ---- CSS Variables ---- */
:root {
    --scifi-cyan: #0ea5e9;
    --scifi-cyan-light: #38bdf8;
    --scifi-cyan-glow: rgba(14, 165, 233, 0.4);
    --scifi-blue-deep: #0284c7;
    --scifi-slate: #1e293b;
    --scifi-slate-light: #334155;
    --scifi-bg: #a8b4c5; /* Dimmed light mode background */
    --scifi-glass: rgba(220, 230, 240, 0.45); /* Less white glass */
    --scifi-glass-border: rgba(14, 165, 233, 0.35);
    --scifi-rose: #f43f5e;
    --scifi-font: 'Rajdhani', sans-serif;
    --scifi-mono: 'Share Tech Mono', 'Courier New', monospace;
}"""

new_root = """/* ---- CSS Variables ---- */
:root {
    --scifi-cyan: #005bb5; /* Gundam Blue */
    --scifi-cyan-light: #4c9aff;
    --scifi-cyan-glow: rgba(0, 91, 181, 0.4);
    --scifi-blue-deep: #e60012; /* Gundam Red */
    --scifi-slate: #1a202c;
    --scifi-slate-light: #4a5568;
    --scifi-bg: #e2e8f0;
    --scifi-glass: rgba(255, 255, 255, 0.90);
    --scifi-glass-border: rgba(0, 91, 181, 0.35);
    --scifi-rose: #ffcc00; /* Gundam Yellow */
    --scifi-font: 'Rajdhani', sans-serif;
    --scifi-mono: 'Share Tech Mono', 'Courier New', monospace;
}"""

content = content.replace(old_root, new_root)

# Replace rgba colors of #0ea5e9 (14, 165, 233) with #005bb5 (0, 91, 181)
content = content.replace('14, 165, 233', '0, 91, 181')

# Replace rgba colors of #0284c7 (2, 132, 199) with #e60012 (230, 0, 18)
content = content.replace('2, 132, 199', '230, 0, 18')

# Replace rgba colors of #38bdf8 (56, 189, 248) with #4c9aff (76, 154, 255)
content = content.replace('56, 189, 248', '76, 154, 255')

with open(file_path, 'w') as f:
    f.write(content)

print("Replaced colors successfully.")
