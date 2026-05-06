# Localhost dev certificates creation


```
openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout m8_app.key -out m8_app.crt -config m8_app.conf -passin pass:"df13d2f2g1d84df64g3s1f1s23d1ZZFFAQZQDGG321FQF321FZQF231FZQ213QFQZ_ZFF32dsdFsgfjugkjkcvbcv-vxcvsesd"
```

best use this
```
openssl req -x509 -newkey rsa:2048 -nodes -keyout m8_app_key.pem -out m8_app_crt.pem -days 365 -config m8_app.conf -extensions v3_ca -passin pass:"df13d2f2g1d84df64g3s1f1s23d1ZZFFAQZQDGG321FQF321FZQF231FZQ213QFQZ_ZFF32dsdFsgfjugkjkcvbcv-vxcvsesd"
```

create pfx
```
openssl pkcs12 -export -out m8_app.pfx -inkey m8_app.key -in m8_app.crt
```