+++
title = "रसिद"
about = "रकम बुझेको रसिद: रकम अक्षरमा समेत, नम्बर सहित र अभिलेखमा दर्ता"
series = "RCT"
party = "received_from"
amount = "amount"

[fields]
issuer = {label = "तपाईंको व्यवसाय (वा नाम)", me = "business|name", required = true}
issuer_address = {label = "त्यसको ठेगाना", me = "business_address|address"}
issuer_pan = {label = "तपाईंको स्थायी लेखा नम्बर (PAN)", me = "pan"}
received_from = {label = "रकम बुझाउनेको नाम", required = true}
amount = {kind = "money", label = "रकम", required = true}
purpose = {label = "के बापत: बीजक नं. INV-2083/84-0007, फर्निचरको अग्रिम", required = true}
method = {label = "भुक्तानीको माध्यम: नगद, चेक नं. १२३४५६, बैंक ट्रान्सफर"}
receiver = {label = "रकम बुझिलिनेको नाम", me = "name"}
+++

# {{issuer}}

{{#issuer_address}}{{issuer_address}}

{{/issuer_address}}{{#issuer_pan}}स्थायी लेखा नं. (PAN): {{issuer_pan}}

{{/issuer_pan}}## रसिद

| रसिद नं.: {{number}}
| मिति: {{date_full}}

| रकम बुझाउनेको नाम: **{{received_from}}**
| रकम: **रु. {{amount}}**
| अक्षरेपी: {{amount_words}}
| प्रयोजन: {{purpose}}{{#method}}
| भुक्तानीको माध्यम: {{method}}{{/method}}

उपर्युक्त रकम बुझिलिएको बेहोरा प्रमाणित गरिन्छ।

| ....................
| रकम बुझिलिनेको दस्तखत{{#receiver}}
| {{receiver}}{{/receiver}}
