+++
title = "निवेदन"
about = "कार्यालय, विद्यालय, बैंक वा संस्थालाई लेखिने औपचारिक निवेदन"

[fields]
to_title = {label = "जसलाई लेखिएको हो, पदले: प्रधानाध्यापक, शाखा प्रबन्धक", required = true}
to_office = {label = "उहाँको कार्यालय वा संस्था", required = true}
to_address = {label = "त्यसको ठेगाना"}
subject = {label = "विषय: चारित्रिक प्रमाणपत्र उपलब्ध गराइदिने सम्बन्धमा।", required = true}
body = {kind = "para", label = "के अनुरोध गर्नुभएको हो र किन, आफ्नै शब्दमा", required = true}
name = {label = "तपाईंको नाम", me = "name", required = true}
address = {label = "तपाईंको ठेगाना", me = "address"}
phone = {label = "तपाईंको फोन", me = "phone"}
email = {label = "तपाईंको इमेल", me = "email"}
+++

मिति: {{date_full}}

| श्रीमान् {{to_title}}ज्यू,
| {{to_office}}{{#to_address}},
| {{to_address}}{{/to_address}}।

**विषय: {{subject}}**

महोदय,

{{body}}

अतः उपर्युक्त बेहोरा मनन गरी आवश्यक कारबाही गरिदिनुहुन सादर अनुरोध गर्दछु।

निवेदक

| दस्तखत: ....................
| नाम: {{name}}{{#address}}
| ठेगाना: {{address}}{{/address}}{{#phone}}
| सम्पर्क नं.: {{phone}}{{/phone}}{{#email}}
| इमेल: {{email}}{{/email}}
