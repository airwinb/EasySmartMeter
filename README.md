SmartMeterEasy
===
---
Note: part of it are still in Dutch. Translation is in progress.


Doel
---
---
Het op een makkelijke manier toegankelijke maken van de uitvoer via de P1 poort
van de energiemeter.

Installatie
-----------
---
De software bestaat uit meerdere bestanden: (en om te downloaden druk je op je
rechter muistoets en selecteer je 'Save Link As ...' of iets dergelijks)

Bestanden server deel:

* **script/smartmeterEasy.conf** <br />
Debian locatie: /etc/smartmeterEasy/ <br />
Dit is de configuratie file. Verander de settings voor jouw omgeving.
* **script/smartmeterEasy.py** <br />
Debian locatie: bv. ~/SmartmeterEasy/ <br />
Dit is het server back-end gedeelte. Het leest de P1 meter en zorgt dat de data in de browser zichtbaar en ververst wordt. Dit bestand hoeft niet aangepast te worden.
* **script/smartmeterEasy.sh** <br />
Debian locatie: /etc/init.d/ <br />
Dit is het start en stop script om smartmeterEasy.py als service te draaien. Aanpassingen zijn nodig in het begin van het bestand.

Wanneer je alle noodzakelijke aanpassingen hebt gedaan, en de bestanden op de goede locatie staan, kun je voor Debian (Wheezy) de volgende commando's geven:

	> cd /etc/init.rd
	> chmod 755 smartmeterEasy.sh
	> sudo update-rc.d smartmeterEasy.sh defaults

Het starten van de service zal dan automatisch gaan bij het booten van het systeem. Om handmatig te starten en stoppen:

	> sudo service smartmeterEasy.sh start
	en
	> sudo service smartmeterEasy.sh stop
	
Bestanden hosting deel:

* **data.php** <br />
Dit is een php file dat ervoor zorgt dat de data in de browser zichtbaar en ververst wordt.
* **day.css** <br />
Dit is de style sheet die voor een groot gedeelte het uiterlijk van de html pagina bepaald. Aanpassingen zijn niet nodig, maar indien je dit wenst kun je de 'look' wel veranderen.
* **index.html** <br />
Dit is een html pagina die het (dag)overzicht geeft.

Verder heb je waar deze twee bestanden staan ook nog de directory 'javascript/rgraph' nodig met alle rgraph javascript libraries.


Issues en release notes
---
---
See Issues and Milestones
