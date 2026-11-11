+++
title = "वडा कार्यालयमा निवेदन"
about = "वडा कार्यालयलाई गुनासो वा अनुरोध (बाटो, ढल, सिफारिस); साधारण निवेदन हो, वडाको आफ्नै फाराम होइन"

[fields]
municipality = {label = "नगरपालिका वा गाउँपालिका: काठमाडौँ महानगरपालिका", required = true}
ward_no = {label = "वडा नम्बर", required = true}
district = {label = "जिल्ला"}
subject = {label = "विषय: शान्तिनगरको बाटो मर्मत गरिदिने सम्बन्धमा।", required = true}
body = {kind = "para", label = "के समस्या वा आवश्यकता हो, कहाँ, कहिलेदेखि", required = true}
name = {label = "तपाईंको नाम", me = "name", required = true}
address = {label = "तपाईंको ठेगाना", me = "address"}
phone = {label = "तपाईंको फोन", me = "phone"}
citizenship_no = {label = "नागरिकता प्रमाणपत्र नम्बर, काममा चाहिने भए"}
+++

मिति: {{date_full}}

| श्रीमान् वडा अध्यक्षज्यू,
| {{municipality}}, {{ward_no}} नं. वडा कार्यालय{{#district}},
| {{district}}{{/district}}।

**विषय: {{subject}}**

महोदय,

उपर्युक्त सम्बन्धमा मेरो निवेदन निम्नानुसार रहेको छ।

{{body}}

अतः उल्लिखित बेहोरा बुझी आवश्यक कारबाही गरिदिनुहुन सादर अनुरोध गर्दछु।

निवेदक

| दस्तखत: ....................
| नाम: {{name}}{{#address}}
| ठेगाना: {{address}}{{/address}}{{#citizenship_no}}
| नागरिकता प्रमाणपत्र नं.: {{citizenship_no}}{{/citizenship_no}}{{#phone}}
| सम्पर्क नं.: {{phone}}{{/phone}}
