# Chinook Database Schema & Tool Coverage

## Tables With Tool Access

### Artist (275 rows)
| ArtistId | Name |
|---|---|
| 1 | AC/DC |
| 2 | Accept |

*Queried by: `get_albums_by_artist`, `get_tracks_by_artist` (via JOIN)*

### Album (347 rows)
| AlbumId | Title | ArtistId |
|---|---|---|
| 1 | For Those About To Rock We Salute You | 1 |
| 2 | Balls to the Wall | 2 |

*Queried by: `get_albums_by_artist`, `get_tracks_by_artist` (via JOIN)*

### Track (3,503 rows)
| TrackId | Name | AlbumId | MediaTypeId | GenreId | Composer | Milliseconds | Bytes | UnitPrice |
|---|---|---|---|---|---|---|---|---|
| 1 | For Those About To Rock (We Salute You) | 1 | 1 | 1 | Angus Young, Malcolm Young, Brian Johnson | 343719 | 11170334 | 0.99 |
| 2 | Balls to the Wall | 2 | 2 | 1 | U. Dirkschneider, W. Hoffmann... | 342562 | 5510424 | 0.99 |

*Queried by: `get_tracks_by_artist` (only Name + ArtistName), `check_for_songs` (all columns)*

### Customer (59 rows)
| CustomerId | FirstName | LastName | Company | Address | City | State | Country | PostalCode | Phone | Fax | Email | SupportRepId |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Luís | Gonçalves | Embraer - Empresa Brasileira... | Av. Brigadeiro Faria Lima, 2170 | São José dos Campos | SP | Brazil | 12227-000 | +55 (12) 3923-5555 | +55 (12) 3923-5566 | luisg@embraer.com.br | 3 |
| 2 | Leonie | Köhler | *None* | Theodor-Heuss-Straße 34 | Stuttgart | *None* | Germany | 70174 | +49 0711 2842222 | *None* | leonekohler@surfeu.de | 5 |

*Queried by: `get_customer_info` (all columns)*

---

## Tables With NO Tool Access

### Genre (25 rows)
| GenreId | Name |
|---|---|
| 1 | Rock |
| 2 | Jazz |

### MediaType (5 rows)
| MediaTypeId | Name |
|---|---|
| 1 | MPEG audio file |
| 2 | Protected AAC audio file |

### Invoice (412 rows)
| InvoiceId | CustomerId | InvoiceDate | BillingAddress | BillingCity | BillingState | BillingCountry | BillingPostalCode | Total |
|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 2021-01-01 | Theodor-Heuss-Straße 34 | Stuttgart | *None* | Germany | 70174 | 1.98 |

### InvoiceLine (2,240 rows)
| InvoiceLineId | InvoiceId | TrackId | UnitPrice | Quantity |
|---|---|---|---|---|
| 1 | 1 | 2 | 0.99 | 1 |

### Employee (8 rows)
| EmployeeId | LastName | FirstName | Title | ReportsTo | BirthDate | HireDate | ... |
|---|---|---|---|---|---|---|---|
| 1 | Adams | Andrew | General Manager | *None* | 1962-02-18 | 2002-08-14 | ... |
| 2 | Edwards | Nancy | Sales Manager | 1 | 1958-12-08 | 2002-05-01 | ... |

### Playlist (18 rows)
| PlaylistId | Name |
|---|---|
| 1 | Music |
| 2 | Movies |

### PlaylistTrack (8,715 rows)
| PlaylistId | TrackId |
|---|---|
| 1 | 3402 |
| 1 | 3389 |

---

## Tool → Query Mapping

### `get_albums_by_artist(artist: str)`
```sql
SELECT Album.Title, Artist.Name
FROM Album JOIN Artist ON Album.ArtistId = Artist.ArtistId
WHERE Artist.Name LIKE '%{artist}%'
```
Returns: album title + artist name only.

### `get_tracks_by_artist(artist: str)`
```sql
SELECT Track.Name as SongName, Artist.Name as ArtistName
FROM Album
LEFT JOIN Artist ON Album.ArtistId = Artist.ArtistId
LEFT JOIN Track ON Track.AlbumId = Album.AlbumId
WHERE Artist.Name LIKE '%{artist}%'
```
Returns: song name + artist name only.

### `check_for_songs(song_title: str)`
```sql
SELECT * FROM Track WHERE Name LIKE '%{song_title}%'
```
Returns: all 9 Track columns (but GenreId/MediaTypeId are raw integers, not resolved to names).

### `get_customer_info(customer_id: int)`
```sql
SELECT * FROM Customer WHERE CustomerID = {customer_id}
```
Returns: all 13 Customer columns including full PII.
