inventory/validate.py içindeki load_items güven sınırında doğrulama yapmıyor. Sözleşme: her girdi sözlük olmalı; 'name' string olmalı ve 'price' sayısal ve 0'dan büyük olmalı. Kural ihlalinde inventory.errors.InventoryError yükselt ve mesaj tam olarak şu olsun:
- name eksik/string değilse: "item <index>: name required"
- price sayısal değilse veya <= 0 ise: "item <index>: price must be positive"
<index> girdinin 0-tabanlı sırası. Geçerli girdide {"name", "price"} içeren liste döndür.
