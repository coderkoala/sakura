+++
title = "Salary certificate"
about = "an employer certifying someone's post and monthly salary (for a bank, a visa, a landlord)"

[fields]
employer = {label = "the employer (your business)", me = "business", required = true}
employer_address = {label = "its address", me = "business_address|address"}
employee = {label = "the employee's name", required = true}
position = {label = "their post", required = true}
joined = {kind = "date", label = "the day they joined", required = true}
salary = {kind = "money", label = "their monthly salary", required = true}
signer = {label = "who signs it", me = "name", required = true}
signer_position = {label = "the signer's post: Managing Director"}
+++

# {{employer}}

{{#employer_address}}{{employer_address}}

{{/employer_address}}Date: {{date_full}}

## To whom it may concern

This is to certify that **{{employee}}** has been employed at {{employer}} as **{{position}}** since {{joined_local}}. The monthly salary is **Rs. {{salary}}** ({{salary_words}}).

This certificate is issued at the request of the employee.

| ....................
| {{signer}}{{#signer_position}}
| {{signer_position}}{{/signer_position}}
| {{employer}}
