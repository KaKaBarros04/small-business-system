// CompanySwitch.jsx
import { useEffect, useState } from "react";
import { api, getActiveCompanyId, setActiveCompanyId } from "./api";

export default function CompanySwitch({ onChanged }) {
  const [companies, setCompanies] = useState([]);
  const [activeId, setActiveId] = useState(getActiveCompanyId() || "");
  const [loading, setLoading] = useState(false);

  async function loadCompanies() {
    setLoading(true);
    try {
      const list = await api.listMyCompanies();
      setCompanies(list || []);

      // se não tem active definido, escolhe o primeiro
      const stored = getActiveCompanyId();
      if (!stored && list?.length) {
        setActiveCompanyId(list[0].id);
        setActiveId(String(list[0].id));
        onChanged?.(list[0]);
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadCompanies();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function changeCompany(idStr) {
    const id = Number(idStr || 0);
    if (!id) return;

    setLoading(true);
    try {
      setActiveCompanyId(id);
      setActiveId(String(id));

      // opcional: valida
      let company = null;
      try {
        company = await api.getMyCompany();
      } catch {}

      onChanged?.(company);

      // ✅ simples e certeiro: recarrega para refletir tudo
      window.location.reload();
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="companySwitch">
      <span className="companySwitchLabel">Empresa</span>

      <select
        value={String(activeId)}
        onChange={(e) => changeCompany(e.target.value)}
        disabled={loading || companies.length <= 1}
      >
        {companies.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name || c.slug || `Empresa ${c.id}`}
          </option>
        ))}
      </select>
    </div>
  );
}