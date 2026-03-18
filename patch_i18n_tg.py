import re

file_path = "app/core/i18n.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

replacements = [
    # RU leftovers
    ('Товар уже существует: <b>{sku}</b> — {name}\\n', 'Товар уже существует: <b>{sku}</b>\\n'),
    ('Название: <b>{name}</b>\\n\\nВведите цену', 'SKU: <b>{sku}</b>\\n\\nВведите цену'),
    ('📦 <b>{sku}</b> — {name}\\n\\nСколько', '📦 <b>{sku}</b>\\n\\nСколько'),
    
    # TG leftovers
    ('Ном: {name}\\n\\nАкнун <b>нарх</b>', 'SKU: {sku}\\n\\nАкнун <b>нарх</b>'),
    ('Ном: <b>{name}</b>\\n\\nНархи воҳидро', 'SKU: <b>{sku}</b>\\n\\nНархи воҳидро'),
    ('Маҳсулот: {name}\\n➕', 'SKU: {sku}\\n➕'),
    ('Маҳсулот: {name}, Миқдор: {qty}', 'SKU: {sku}, Миқдор: {qty}'),
    ('Маҳсулот: {name}\\nМиқдор: {qty}', 'SKU: {sku}\\nМиқдор: {qty}'),
    ('Маҳсулот: {name} ({sku})\\nМиқдор: {qty}', 'SKU: {sku}\\nМиқдор: {qty}'),
    ('Маҳсулот: <b>{name}</b>\\nМиқдор: {qty}', 'SKU: <b>{sku}</b>\\nМиқдор: {qty}'),
    ('Маҳсулот: {sku} — {name}\\nМиқдор: {qty}', 'SKU: {sku}\\nМиқдор: {qty}'),
    ('Маҳсулот: {name} ({qty} дона)', 'SKU: {sku} ({qty} дона)'),
    ('Мол аллакай мавҷуд аст: <b>{sku}</b> — {name}\\n', 'Мол аллакай мавҷуд аст: <b>{sku}</b>\\n'),
    ('📦 <b>{sku}</b> — {name}\\n\\nЧанд', '📦 <b>{sku}</b>\\n\\nЧанд'),
]

for old, new in replacements:
    content = content.replace(old, new)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("i18n TG patched.")
