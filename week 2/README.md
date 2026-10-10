# Sales Analytics -- UrbanStyle.ltd Andmemeeskond
   ## Meeskonnaliikmed
   | Nimi | Roll (Nädal 2) |
   
   | Oliver Dalberg | A: Müügiandmed |
   
   | Helena Toompalu | B: Kliendiandmed |

   | Kristina Piltjai | C: Tooted |


## Tiimi esitlus
[Vaata esitlust PDF-formaadis](Week 2 grupitöö.pdf)

## Mida uurisime/õppisime
Kristina - tegin products_test toodeandmete puhastamist. Kõigepealt lõin test koopia, seejärel vaatasin mitu rida kokku on ning palju duplikaate on. Selgus, et on 362 rida, millest on 12 duplikaatse tootenimega ja kõigil neil on 2 koopiate arvu. NULL väärtused kriitilistes väljundites puudusid. Samuti polnud ebareaalseid ega äärmuslikke hindu. Soovitan Toomaselt duplikaadid tabelist eemaldada, et saaks selgema pildi toodete olukorrast.

Helena - korrastasin customers_test tabelit ning otsisin duplikaate ja puuduolevaid andmeid. Klientide tabelis oli 3150 rida ja duplikaatseid e-maile 130. Puuduva ees- või perenimega kliente ei esinenud. Linnanimede kujud varieeruvad - kokku 12 linna kohta 54 erinevat nimekuju. Puuduvaid telefoninumbreid kontaktandmetes ei esine, küll aga on puudu 380 e-maili aadressi. Vaja oleks andmed puhastada duplikaatidest ning olemasolevad andmed ühtlustada.

Oliver - uurisin sales tabelit tehes sellest esialgu sales_test koopia. Müügiandmetes esines suurel hulgal duplikaate. Kokku oli 15234 rida millest 5116 rida olid duplikaadid ehk siis 33%. Kui vaadata käibe numbreid siis enne duplikaate oli see 4.37M € ning peale duplikaadid moodustasid selles 1.47M € seega reaalne käive oli tegelikult 2.9M €. NULL väärtusi esines customer_id veerus kuid need võivad olla tuvastamata ostjad, saab parandada lisades väärtus nagu ´anonüümne´ aga hetkel kriitiline ei ole. Muud andmed tundusid korras olevat.

| Kategooria         | Leitud probleeme | Kirjeldus                                           |
| ------------------ | ---------------- | --------------------------------------------------- |
| Duplikaadid        | 5116             | Korduvad invoice_id väärtused (duplikaattellimused) |
| NULL customer_id   | 1487             | Puuduv kliendi viide                                |
| NULL sale_date     | 0                | Puuduv kuupäev                                      |
| NULL total_price   | 0                | Puuduv summa                                        |
| Tuleviku kuupäevad | 0                | Kuupäev > tänane                                    |
| KOKKU probleeme    | 6603             |                                                     |

