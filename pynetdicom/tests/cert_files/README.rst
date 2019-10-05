Instruction for creating new testing certificates
-------------------------------------------------

Using a Certificate Authority
.............................

1. Create Certificate Authority (CA) key and certificate

`openssl genrsa -out ca.key 4096`
`openssl req -new -x509 -days 3650 -key ca.key -out ca.crt -nodes`

Country Name (2 letter code) [AU]:.
State or Province Name (full name) [Some-State]:.
Locality Name (eg, city) []:.
Organization Name (eg, company) [Internet Widgits Pty Ltd]:pynetdicom
Organizational Unit Name (eg, section) []:pydicom
Common Name (e.g. server FQDN or YOUR name) []:pynetdicom-ca
Email Address []:.

2. Create server key, CSR and self-signed certificate

`openssl genrsa -out server.key 4096`
`openssl req -new -key server.key -out server.csr`

Country Name (2 letter code) [AU]:.
State or Province Name (full name) [Some-State]:.
Locality Name (eg, city) []:.
Organization Name (eg, company) [Internet Widgits Pty Ltd]:pynetdicom
Organizational Unit Name (eg, section) []:pydicom
Common Name (e.g. server FQDN or YOUR name) []:pynetdicom-server
Email Address []:.

Please enter the following 'extra' attributes
to be sent with your certificate request
A challenge password []:
An optional company name []:

`openssl x509 -req -days 3650 -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out server.crt`

3. Create client key and CSR

`openssl genrsa -out client.key 4096`
`openssl req -new -key client.key -out client.csr`

`openssl x509 -req -days 3650 -in client.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out client.crt`

4. Usage

Server SSLContext

context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
context.verify_mode = ssl.CERT_REQUIRED
context.load_cert_chain(certfile=SERVER_CERT, keyfile=SERVER_KEY)
context.load_verify_locations(cafile=CA_CERT)

Client SSLContext

context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH, cafile=SERVER_CERT)
context.verify_mode = ssl.CERT_REQUIRED
context.load_cert_chain(certfile=CLIENT_CERT, keyfile=CLIENT_KEY)
context.load_verify_locations(cafile=CA_CERT)


No Certificate Authority
........................

1. Server

`openssl req -new -newkey rsa:4096 -days 3650 -nodes -x509 -keyout server.key -out server.crt`

2. Client

`openssl req -new -newkey rsa:4096 -days 3650 -nodes -x509 -keyout client.key -out client.crt`

3. Usage

Server SSLContext

context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
context.verify_mode = ssl.CERT_REQUIRED
context.load_cert_chain(certfile=SERVER_CERT, keyfile=SERVER_KEY)
context.load_verify_locations(cafile=CLIENT_CERT)

Client SSLContext

context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH, cafile=SERVER_CERT)
context.verify_mode = ssl.CERT_REQUIRED
context.load_cert_chain(certfile=CLIENT_CERT, keyfile=CLIENT_KEY)
