EasySmartMeter
==============

Note: part of it are still in Dutch. Translation is in progress.


Doel
----
Het op een makkelijke manier toegankelijke maken van de uitvoer via de P1 poort
van de energiemeter.


Installatie
-----------

Tijdelijke installatie aanwijzingen staan in install.txt

De software bestaat uit drie bestanden: (en om te downloaden druk je op je rechter muistoets en selecteer je 'Save Link As ...' of iets dergelijks)

    p1_service.py; een python script dat altijd moet draaien en zorgt dat de gegevens in een bruikbaar formaat worden weggeschreven
    data.php; een php file dat ervoor zorgt dat de data in de browser zichtbaar en ververst wordt
    index.html; een html pagina die het (dag)overzicht geeft

Het bestand p1_service.py kun je plaatsen waar je wilt, maar deze moet wel altijd lopen. De bestanden data.php en index.html moeten 'gehost' worden. Verder heb je waar deze twee bestanden staan ook nog de directory 'javascript/rgraph' nodig met alle rgraph javascript libraries.

Het p1_service.py programma maakt gebruik van de volgende locatie voor de data bestanden:

    /mnt/p1tmpfs/data; hier staan de data bestanden
    /mnt/p1tmpfs/log; hier staat de file p1.log waarin de log output van het python script staat

Issues en release notes
-----------------------
See Issues and the Milestones
