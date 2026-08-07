def format_angka_rupiah(nilai, desimal=False):
	if nilai is None:
		return "-"

	if desimal:
		angka = f"{float(nilai):,.2f}"
	else:
		angka = f"{int(float(nilai)):,}"

	return angka.replace(",", "X").replace(".", ",").replace("X", ".")
