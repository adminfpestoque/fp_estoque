from pathlib import Path

path = Path(__file__).resolve().parents[1] / "frontend/src/pages/products.jsx"
text = path.read_text(encoding="utf-8")
old = '''      setPackagingTypes((current) => [...current.filter((item) => item.id !== created.id), created].sort((a, b) => a.name.localeCompare(b.name, "pt-BR")));
      setNewPackagingType("");
      choosePackagingType(created.id);
      notify(`Tipo de embalagem “${created.name}” criado e selecionado.`);
'''
new = '''      setPackagingTypes((current) => [...current.filter((item) => item.id !== created.id), created].sort((a, b) => a.name.localeCompare(b.name, "pt-BR")));
      setNewPackagingType("");
      setForm((current) => ({
        ...current,
        packaging: {
          packaging_type: String(created.id),
          packaging_type_name: created.name,
          units_per_package: String(defaultUnitsForType(created.name)),
          cost_price: "0,00",
          sale_price: "0,00",
        },
      }));
      notify(`Tipo de embalagem “${created.name}” criado e selecionado.`);
'''
if old not in text:
    raise RuntimeError("Trecho de criação de tipo não encontrado em products.jsx")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
