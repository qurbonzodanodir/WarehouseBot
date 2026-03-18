import re

file_path = "app/core/i18n.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Keys that need product {name} removed. We need to be careful with formatting.
replacements = [
    # RU
    ('Товар: {name}\\n➕ Добавлено: {qty}', 'Товары (SKU: {sku})\\n➕ Добавлено: {qty}'),
    ('<code>{sku}</code> — {name} | {price} сом', '<code>{sku}</code> | {price} сом'),
    ('Название: {name}\\n\\nТеперь введите <b>цену</b>', 'SKU: {sku}\\n\\nТеперь введите <b>цену</b>'),
    ('Название: {name}\\nЦена: {amount}', 'Цена: {amount}'),
    ('📦 <b>{name}</b>\\n(SKU: <code>{sku}</code>)', '📦 <b>Товар (SKU: {sku})</b>'),
    ('<b>{sku}</b> — {name} (В наличии:', '<b>{sku}</b> (В наличии:'),
    ('Товар: {name}, Кол-во: {qty}', 'SKU: {sku}, Кол-во: {qty}'),
    ('date} | {name} | {qty} шт', 'date} | SKU: {sku} | {qty} шт'),
    ('Товар: {name}\\nКол-во: {qty}', 'SKU: {sku}\\nКол-во: {qty}'),
    ('<b>{sku}</b> — {name}\\nВведите', '<b>{sku}</b>\\nВведите'),
    ('Товар: {name} ({sku})\\n', 'SKU: {sku}\\n'),
    ('Товар: <b>{name}</b>\\nКол-', 'SKU: <b>{sku}</b>\\nКол-'),
    ('Товар: {sku} — {name}\\n', 'SKU: {sku}\\n'),
    ('Склад: {store}\\nТовар: {name} ({qty}', 'Склад: {store}\\nSKU: {sku} ({qty}'),
    ('{sku} — {name}: <b>{qty}</b>', '{sku}: <b>{qty}</b>'),
    ('Товар: {sku} — {name}\\nКол-', 'SKU: {sku}\\nКол-'),
    ('📦 <b>{sku}</b> — {name}\\n\\nВведите', '📦 <b>{sku}</b>\\n\\nВведите'),
    ('📦 {name} (<code>{sku}</code>)\\n➕', '📦 <b>{sku}</b>\\n➕'),
    ('📦 <b>{sku}</b> — {name}\\n💰', '📦 <b>{sku}</b>\\n💰'),
    ('📦 <b>{sku}</b> — {name}\\n🔢', '📦 <b>{sku}</b>\\n🔢'),
    ('📦 {name} (<code>{sku}</code>)\\n📋', '📦 <b>{sku}</b>\\n📋'),
    
    # TG
    ('Мол: {name}\\n➕ Илова шуд: {qty}', 'Мол (SKU: {sku})\\n➕ Илова шуд: {qty}'),
    ('<code>{sku}</code> — {name} | {price}', '<code>{sku}</code> | {price}'),
    ('Ном: {name}\\n\\nАкнун <b>нархро</b>', 'SKU: {sku}\\n\\nАкнун <b>нархро</b>'),
    ('Ном: {name}\\nНарх: {amount}', 'Нарх: {amount}'),
    ('📦 <b>{name}</b>\\n(SKU: <code>{sku}</code>)', '📦 <b>Мол (SKU: {sku})</b>'),
    ('<b>{sku}</b> — {name} (Дар анбор:', '<b>{sku}</b> (Дар анбор:'),
    ('Мол: {name}, Миқдор: {qty}', 'SKU: {sku}, Миқдор: {qty}'),
    ('date} | {name} | {qty} дона', 'date} | SKU: {sku} | {qty} дона'),
    ('Мол: {name}\\nМиқдор: {qty}', 'SKU: {sku}\\nМиқдор: {qty}'),
    ('<b>{sku}</b> — {name}\\nМиқдори', '<b>{sku}</b>\\nМиқдори'),
    ('Мол: {name} ({sku})\\n', 'SKU: {sku}\\n'),
    ('Мол: <b>{name}</b>\\nМиқдор:', 'SKU: <b>{sku}</b>\\nМиқдор:'),
    ('Мол: {sku} — {name}\\n', 'SKU: {sku}\\n'),
    ('Анбор: {store}\\nМол: {name} ({qty}', 'Анбор: {store}\\nSKU: {sku} ({qty}'),
    ('Мол: {sku} — {name}\\nМиқдор:', 'SKU: {sku}\\nМиқдор:'),
    ('📦 <b>{sku}</b> — {name}\\n\\nМиқдорро', '📦 <b>{sku}</b>\\n\\nМиқдорро'),
    ('📦 {name} (<code>{sku}</code>)\\n➕', '📦 <b>{sku}</b>\\n➕'),
    ('📦 <b>{sku}</b> — {name}\\n💰', '📦 <b>{sku}</b>\\n💰'),
    ('📦 <b>{sku}</b> — {name}\\n🔢', '📦 <b>{sku}</b>\\n🔢'),
    ('📦 {name} (<code>{sku}</code>)\\n📋', '📦 <b>{sku}</b>\\n📋'),
]

for old, new in replacements:
    content = content.replace(old, new)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("i18n patched.")
