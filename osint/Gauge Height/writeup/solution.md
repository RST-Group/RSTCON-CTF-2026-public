# Gauge Height  -  Solution

## Step 1: read the export header

```
# RST Hydro historian export
# upstream feed: agency=USGS site=09421500
# parameters: 00060=streamflow(cfs) 00065=gage_height(ft)
```

Three identifiers stand out:

- `agency=USGS`  -  the data originates from the US Geological Survey.
- `site=09421500`  -  a USGS National Water Information System (NWIS) site
  number. These are public and globally unique.
- `00060` / `00065`  -  USGS parameter codes. `00060` is discharge in cubic feet
  per second, `00065` is gage height in feet. They confirm this is NWIS data and
  tell you it is a streamgage.

## Step 2: resolve the site

Look the site number up directly:

```
https://waterdata.usgs.gov/monitoring-location/09421500/
```

or search `USGS 09421500`. It resolves to:

```
Colorado River below Hoover Dam, AZ-NV   (USGS 09421500)
```

The gage is operated in cooperation with the US Bureau of Reclamation, Lower
Colorado Region.

## Step 3: format

The landmark the site sits below is Hoover Dam.

Flag Submission is done via pin on a map. Latitude and Longitude of the Hover Dam is 36.0158268,-114.7384582.

