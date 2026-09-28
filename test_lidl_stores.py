from config.lidl_stores import LIDL_STORES


print(f"Configured Lidl stores: {len(LIDL_STORES)}")
print()

for index, store in enumerate(
    LIDL_STORES,
    start=1,
):
    print(f"{index}. {store['name']}")
    print(f"   {store['address']}")
    print(f"   {store['postal_code']} {store['city']}")
    print(f"   {store['store_page']}")
    print()