+++
title = "Quotation"
about = "a price quotation with line items and VAT 13% (or --pan-only), numbered"
items = true
series = "QTN"
party = "buyer"

[fields]
seller = {label = "your business (or your name)", me = "business|name", required = true}
seller_address = {label = "its address", me = "business_address|address"}
seller_pan = {label = "your PAN/VAT registration number", me = "pan", required = true}
seller_phone = {label = "your phone", me = "phone"}
buyer = {label = "who asked for the prices", required = true}
buyer_address = {label = "their address"}
valid_days = {label = "how many days the prices hold", default = "15"}
note = {label = "terms: delivery within 7 days, 50% advance"}
+++

# {{seller}}

| {{tax_id_label}}: {{seller_pan}}{{#seller_address}}
| {{seller_address}}{{/seller_address}}{{#seller_phone}}
| Phone: {{seller_phone}}{{/seller_phone}}

## Quotation

| Quotation No.: {{number}}
| Date: {{date_full}}

| To: **{{buyer}}**{{#buyer_address}}
| Address: {{buyer_address}}{{/buyer_address}}

We are pleased to quote the following prices.

{{items_table}}

**In words:** {{total_words}}

These prices hold for {{valid_days}} days from the date above.

{{#note}}{{note}}

{{/note}}| ....................
| For {{seller}}
