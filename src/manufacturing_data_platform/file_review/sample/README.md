# Bundled public sample

Derived from [MetroPT-3, UCI](https://archive.ics.uci.edu/dataset/791/metropt%203%20dataset),
Davari, N., Veloso, B., Ribeiro, R., & Gama, J. (2021), DOI
[10.24432/C5VW3R](https://doi.org/10.24432/C5VW3R), under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

`metropt3-day.csv` contains the 7,144 source rows dated 2020-02-01, converted from wide columns
to 21,432 observations of TP2 (bar), Oil_temperature (°C), and Motor_current (A). Numeric text is
unchanged. A `T` replaces the date/time space; no timezone is invented. The equipment label is
added for this sample. Blank quality indicates that source sensor quality is not available.
This adaptation is not endorsed by the source authors.

`provenance.json` records the source/archive identity, selection and sample SHA-256. The application
checks that sample digest before every import. The complete 208 MiB source is not needed to run it.
Source intervals and operating values describe a historical train compressor; they do not demonstrate
a current factory connection, failure diagnosis, or this service's production adoption.
