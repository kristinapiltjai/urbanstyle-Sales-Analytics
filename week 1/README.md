# Sales Analytics -- UrbanStyle.ltd Andmemeeskond
   ## Meeskonnaliikmed
   | Nimi | Roll (Nädal 1) |
   
   | Helena Toompalu | A: Müügiandmed |
   
   | Kristina Piltjai | B: Kliendiandmed |

   | Oliver Dalberg | C: Tooted |


## Tiimi esitlus
[Vaata esitlust PDF-formaadis](Week 1 grupitöö.pdf)

## Mida uurisime/õppisime
Kristina - uurisin SQL-s palju kliente kokku ning mis linnadest kliendid on ja mis andmeid klientide kohta olemas on. Näiteks puudus 380 kliendil e-mailid. Soovitasin Toomasel puudu olevad e-mailid välja uurida. Kõige suurem mure koht sellel nädalal oli minu jaoks VS Code ja Githubi ühenduse loomine, aga pusisin ning sain hakkama.

Oliver - uurisin urbanstyle toodete tabelit. Kokkuvõtvalt liiga palju tooteid ei olnud (362), mis omakorda jagunesid 5 kategooria vahel üpriski võrdselt (67-82 tooded ühes kategoorias). Tarnijaid omakorda oli nende toodete peale 15. Tootegruppide keskmine hinnaklass ei olnud väga madal kuid samas mitte ka kõrge nt. jalanõudel 214.10€.Võiks pakkuda mingil määral butiik tüüpi pood. Huvi pärast uurisin ka brutokasumi marginaale ja üle gruppide olid need väga sarnased ~33% üldise keskmise hinna järgi arvutades. Duplikaate tundus olevat 12 kirje jagu st. kattusid product_name, category, retail_price, mis annab üsa suure kindluse duplikaatide õigsuses. Üldiselr soovitaks tabelid korrastada duplikaatise osas, eco_certified veerus olid mõned NULL väärtused kuid hetkel seda liiga oluliseks ei pea kuna andmed võivadki lihtsalt tootja poolelt puudu olla

Helena - uurisin urbanstyle müügi tabelit. Üllatas, et oli palju negatiivseid tehinguid üsna suurtes summades, neist suurim -1405.32. Puudu olid 1487 kliendi andmed. Kui poe asukoht on NULL, viitab see online-müügile - ilus oleks need read ümber nimetada, et oleks kindlam, et mõne poe asukoht puudu ei ole. Arvestatav hulk, kokku ⅓ müükidest, toimub online-keskkonnas. Lisaks tegin VS Code-is Workspace-id erinevate ühenduste haldamiseks