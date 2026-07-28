# Polices embarquees

`app/core/fonts.ensure_inter()` telecharge automatiquement ces fichiers depuis
le repo Google Fonts au premier export PDF :

- `Inter-Regular.ttf`
- `Inter-Bold.ttf`

Source (OFL) : <https://github.com/google/fonts/tree/main/ofl/inter/static>

Si le download echoue (offline, proxy strict), les exports PDF retombent sur
Helvetica avec un warning dans les logs. Les exports DOCX n'ont pas besoin
des TTF (Word substitue cote client a partir du nom de police).
