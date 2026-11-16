# Sales Analytics -- UrbanStyle.ltd Andmemeeskond
   ## Meeskonnaliikmed
   | Nimi | Roll (Nädal 7) |
   
   | Oliver Dalberg | A+B: Data Loading + Cleaning |
   
   | Kristina Piltjai | C: RFM Analysis |

   | Helena Toompalu | D: Visualization |


## Tiimi esitlus


## Mida uurisime/õppisime
Kristina - mina tegin RFM analüüsi. Kuna Python minu jaoks täiesti uus asi, siis tekitab segadust, et mida ja kuidas teha. SQL tundus lihtsam. Aga AI oli väga palju abiks. Viskasin Notebook LM enda osa ülesandest sisse ning ta andis üsna kiiresti vastuse, kuidas ja mida teha. Lisaks meie tiimis Oliver on Pythonit varasemalt kasutanud ning oskas ka palju abiks olla. Saime esimest korda meeskonnana päriselt meeskonna tööd teha. Varasemalt grupitööd pigem nagu iseseisvad tööd ikkagi olnud. Kindlasti tuleks veel rohkem praktiseerida. Ja rääkides tulemustest, siis RFM analüüsist tuli välja, et potentsiaalseid kliente on 759 ning nende osakool on kõige suurem ehk pea 30%. Loojalsed järgnevad arvuga 679 ja osakaal 26.7%. Kõige väiksem osakaal on kadunud ning nende arv on 118 ja osakaal 4.6%. Soovitaks need kadunud ka üles leida ja potentsiaalsetele kindlasti kampaaniaid korraldada uudiskirjade näol.

Oliver - tegin Jupitery esmase setupi ning Supabase ühenduse ning andmete laadimise tabelistest sales, products ja customers ning nende ühendamine ühte data frame´i left join kaudu. Samuti muutsin Supabase seadistustes 100k rea peale andmete sisselugemise ning RLS poolelt lubasin mainitud tabelitel read-only. Lisaks tegin põgusa kvaliteedikontrolli, kus vaatasin invoice_id duplikaate ning üle tabelite NULL väärtuseid. Eemaldasin juhendi kohaselt negatiivsed total_price ning NULL customer_id, sale_date, total_price väärtused. Päris õige see ilmselt ei ole kuna negatiivne total_price võib tähendada tagasiostu, NULL customer_id ilma registreerimata müüki jne. kuid lojaalsustasemete narratiivi osas mõneti okei.