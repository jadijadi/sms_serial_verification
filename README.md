# sms_verification


## TODO
- [x] Farhad seifi https://ngrok.com/
- [x] add db path to config.py.sample
- [x] do more while normalizing, specially against SQLInjection. remove all non alpha numerical
- [ ] Atomic problem when I'm commiting every 10 inserts
- [x] some health check url
- [x] there is problem with JJ1000000 and JJ100
- [x] create requirements.txt (pip freeze)
- [x] the insert will fail if there is a ' or " in excel file
- [x] another 10 % problem :D
- [x] refactor name str in normalize function
- [x] in normalize, convert AB001 to AB00001 (max len? say 15)
- [x] dockerize (alpine? search for uwsgi)
- [x] merge pull requests.. check I mean :)
- [x] do proper inserts with INTO
- [x] templating
- [x] thanks H shafiee
- [x] rate limit
- [x] add call back token on kavenegar site
- [x] we do not normalize the failed serials when importing!
- [x] invalids can have duplicates
- [x] migrate to mysql
- [x] if we have 2 matches on serials, regurn a general OK message
- [x] add altech logo from Downloads/logo.png ; top left
- [x] close db connection in check_serial
- [ ] count the failed insertions in db
- [x] regenerate requirements.txt with MySQLdb
- [ ] proper texts are provided in Downloads/sms_reply_texts
- [ ] is it possible to check a serial from the gui?
- [x] dummy message for end to end test via SMS
- [ ] log all incomming smss

