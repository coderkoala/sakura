+++
title = "दरभाउपत्र"
about = "सामान वा सेवाको दरभाउपत्र (कोटेसन): विवरण, मू.अ.कर १३% (वा --pan-only), नम्बर सहित"
items = true
series = "QTN"
party = "buyer"

[fields]
seller = {label = "तपाईंको व्यवसाय (वा नाम)", me = "business|name", required = true}
seller_address = {label = "त्यसको ठेगाना", me = "business_address|address"}
seller_pan = {label = "तपाईंको स्थायी लेखा नम्बर (PAN) / मू.अ.कर दर्ता नम्बर", me = "pan", required = true}
seller_phone = {label = "तपाईंको फोन", me = "phone"}
buyer = {label = "दरभाउ माग्नेको नाम", required = true}
buyer_address = {label = "उहाँको ठेगाना"}
valid_days = {label = "दरभाउ कति दिन मान्य रहने", default = "15"}
note = {label = "सर्त: ७ दिनभित्र आपूर्ति, ५०% अग्रिम"}
+++

# {{seller}}

| {{tax_id_label}}: {{seller_pan}}{{#seller_address}}
| {{seller_address}}{{/seller_address}}{{#seller_phone}}
| फोन: {{seller_phone}}{{/seller_phone}}

## दरभाउपत्र

| दरभाउपत्र नं.: {{number}}
| मिति: {{date_full}}

| श्री **{{buyer}}**{{#buyer_address}}
| ठेगाना: {{buyer_address}}{{/buyer_address}}

तपाईंको मागबमोजिम निम्नानुसारको दरभाउ पेस गरिएको छ।

{{items_table}}

**अक्षरेपी:** {{total_words}}

यो दरभाउ माथि उल्लिखित मितिले {{valid_days}} दिनसम्म मान्य रहनेछ।

{{#note}}{{note}}

{{/note}}| ....................
| {{seller}} को तर्फबाट
