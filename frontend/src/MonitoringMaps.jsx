import { useEffect, useMemo, useRef, useState } from "react";
import { api, resolveApiUrl } from "./api";
import "./MonitoringMaps.css";

const DEVICE_OPTIONS = [
  { value: "RAT_PVC", label: "Caixa rateira PVC" },
  { value: "RAT_CARDBOARD", label: "Caixa rateira cartão" },
  { value: "COCKROACH_TRAP", label: "Armadilha / detetora de baratas" },
  { value: "INSECT_CATCHER", label: "Inseto-captador" },
  { value: "OTHER", label: "Outro" },
];

const STATUS_OPTIONS = [
  { value: "ND", label: "ND" },
  { value: "D", label: "D" },
  { value: "DI", label: "DI" },
  { value: "NC", label: "NC" },
  { value: "MC", label: "MC" },
  { value: "TC", label: "TC" },
];

function deviceLabel(v) {
  return DEVICE_OPTIONS.find((x) => x.value === v)?.label || v || "—";
}

function markerStyle(deviceType) {
  switch ((deviceType || "").toUpperCase()) {
    case "RAT_PVC":
      return {
        background: "#facc15",
        border: "2px solid #dc2626",
        borderRadius: "999px",
      };

    case "RAT_CARDBOARD":
      return {
        background: "#fde047",
        border: "2px solid #dc2626",
        borderRadius: "4px",
      };

    case "COCKROACH_TRAP":
      return {
        background: "#fca5a5",
        border: "2px solid #dc2626",
        borderRadius: "6px",
        width: 26,
        height: 18,
      };

    case "INSECT_CATCHER":
      return {
        background: "#bfdbfe",
        border: "2px solid #2563eb",
        clipPath: "polygon(50% 0%, 0% 100%, 100% 100%)",
      };

    default:
      return {
        background: "#e5e7eb",
        border: "2px solid #374151",
        borderRadius: "999px",
      };
  }
}

function Marker({ point, onClick }) {
  const extra = markerStyle(point.device_type);
  const width = extra.width || 24;
  const height = extra.height || 24;

  return (
    <button
      type="button"
      className="map-marker"
      title={`Ponto ${point.point_number} - ${deviceLabel(point.device_type)}`}
      onClick={(e) => {
        e.stopPropagation();
        onClick?.(point);
      }}
      style={{
        left: `${point.x_percent}%`,
        top: `${point.y_percent}%`,
        width,
        height,
        ...extra,
      }}
    >
      <span>{point.point_number}</span>
    </button>
  );
}

function emptyVisitRow() {
  return {
    status_code: "ND",
    consumption_percent: "",
    action_taken: "",
    notes: "",
    replaced: false,
  };
}

export default function MonitoringMaps() {
  const [clients, setClients] = useState([]);
  const [selectedClientId, setSelectedClientId] = useState("");
  const [maps, setMaps] = useState([]);
  const [selectedMapId, setSelectedMapId] = useState("");
  const [selectedMap, setSelectedMap] = useState(null);

  const [visits, setVisits] = useState([]);
  const [selectedVisitId, setSelectedVisitId] = useState("");

  const [loadingClients, setLoadingClients] = useState(false);
  const [loadingMaps, setLoadingMaps] = useState(false);
  const [loadingMap, setLoadingMap] = useState(false);
  const [loadingVisits, setLoadingVisits] = useState(false);

  const [savingMap, setSavingMap] = useState(false);
  const [savingPoint, setSavingPoint] = useState(false);
  const [savingVisit, setSavingVisit] = useState(false);

  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const imageWrapRef = useRef(null);

  const [mapForm, setMapForm] = useState({
    name: "",
    page_order: 1,
    notes: "",
    image: null,
  });

  const [pointDraft, setPointDraft] = useState(null);
  const [pointForm, setPointForm] = useState({
    label: "",
    device_type: "RAT_PVC",
  });

  const [editingPoint, setEditingPoint] = useState(null);

  const [visitForm, setVisitForm] = useState({
    pest_type: "",
    notes: "",
    resultsByPointId: {},
  });

  const selectedClient = useMemo(
    () => clients.find((c) => String(c.id) === String(selectedClientId)),
    [clients, selectedClientId]
  );

  function clearMessages() {
    setError("");
    setSuccess("");
  }

  function buildInitialResults(points, existing = {}) {
    const next = { ...existing };
    for (const p of points || []) {
      if (!next[p.id]) {
        next[p.id] = emptyVisitRow();
      }
    }
    return next;
  }

  function resetVisitFormFromMap(mapData) {
    setVisitForm({
      pest_type: selectedClient?.pest_type || "",
      notes: "",
      resultsByPointId: buildInitialResults(mapData?.points || []),
    });
  }

  async function loadClients() {
    setLoadingClients(true);
    clearMessages();
    try {
      const data = await api.listClients();
      setClients(Array.isArray(data) ? data : []);
    } catch (e) {
      setError(e.message || "Erro ao carregar clientes.");
    } finally {
      setLoadingClients(false);
    }
  }

  async function loadMaps(clientId) {
    if (!clientId) {
      setMaps([]);
      setSelectedMapId("");
      setSelectedMap(null);
      return;
    }

    setLoadingMaps(true);
    clearMessages();

    try {
      const data = await api.listClientSiteMaps(clientId);
      const arr = Array.isArray(data) ? data : [];
      setMaps(arr);

      if (arr.length > 0) {
        setSelectedMapId(String(arr[0].id));
      } else {
        setSelectedMapId("");
        setSelectedMap(null);
      }
    } catch (e) {
      setError(e.message || "Erro ao carregar mapas.");
    } finally {
      setLoadingMaps(false);
    }
  }

  async function loadMap(mapId) {
    if (!mapId) {
      setSelectedMap(null);
      return;
    }

    setLoadingMap(true);
    clearMessages();

    try {
      const data = await api.getSiteMap(mapId);
      setSelectedMap(data || null);
      setVisitForm((prev) => ({
        ...prev,
        pest_type: prev.pest_type || selectedClient?.pest_type || "",
        resultsByPointId: buildInitialResults(data?.points || [], prev.resultsByPointId),
      }));
    } catch (e) {
      setError(e.message || "Erro ao carregar mapa.");
    } finally {
      setLoadingMap(false);
    }
  }

  async function loadVisits(clientId) {
    if (!clientId) {
      setVisits([]);
      setSelectedVisitId("");
      return;
    }

    setLoadingVisits(true);
    clearMessages();

    try {
      const data = await api.listMonitoringVisitsByClient(clientId);
      setVisits(Array.isArray(data) ? data : []);
    } catch (e) {
      setError(e.message || "Erro ao carregar visitas.");
    } finally {
      setLoadingVisits(false);
    }
  }

  useEffect(() => {
    loadClients();
  }, []);

  useEffect(() => {
    if (selectedClientId) {
      loadMaps(selectedClientId);
      loadVisits(selectedClientId);
    } else {
      setMaps([]);
      setSelectedMapId("");
      setSelectedMap(null);
      setVisits([]);
      setSelectedVisitId("");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedClientId]);

  useEffect(() => {
    if (selectedMapId) {
      loadMap(selectedMapId);
    } else {
      setSelectedMap(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedMapId]);

  async function handleCreateMap(e) {
    e.preventDefault();
    clearMessages();

    if (!selectedClientId) {
      setError("Escolhe um cliente primeiro.");
      return;
    }

    if (!mapForm.name.trim()) {
      setError("Indica o nome do mapa.");
      return;
    }

    if (!mapForm.image) {
      setError("Escolhe a imagem da planta.");
      return;
    }

    const fd = new FormData();
    fd.append("client_id", String(selectedClientId));
    fd.append("name", mapForm.name.trim());
    fd.append("page_order", String(mapForm.page_order || 1));
    fd.append("notes", mapForm.notes || "");
    fd.append("is_active", "true");
    fd.append("image", mapForm.image);

    setSavingMap(true);
    try {
      const created = await api.createSiteMap(fd);

      setMapForm({
        name: "",
        page_order: 1,
        notes: "",
        image: null,
      });

      await loadMaps(selectedClientId);
      await loadVisits(selectedClientId);

      if (created?.id) {
        setSelectedMapId(String(created.id));
      }

      setSuccess("Mapa criado com sucesso.");
    } catch (e2) {
      setError(e2.message || "Erro ao criar mapa.");
    } finally {
      setSavingMap(false);
    }
  }

  async function handleDeleteMap(mapId) {
    if (!mapId) return;
    if (!window.confirm("Apagar este mapa?")) return;

    clearMessages();
    try {
      await api.deleteSiteMap(mapId);
      await loadMaps(selectedClientId);
      setSuccess("Mapa apagado com sucesso.");
    } catch (e) {
      setError(e.message || "Erro ao apagar mapa.");
    }
  }

  function handleMapClick(e) {
    if (!selectedMap || !imageWrapRef.current) return;

    const rect = imageWrapRef.current.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 100;
    const y = ((e.clientY - rect.top) / rect.height) * 100;

    setPointDraft({
      x_percent: Math.max(0, Math.min(100, Number(x.toFixed(2)))),
      y_percent: Math.max(0, Math.min(100, Number(y.toFixed(2)))),
    });

    setEditingPoint(null);
    setPointForm({
      label: "",
      device_type: "RAT_PVC",
    });
  }

  async function handleCreatePoint(e) {
    e.preventDefault();
    clearMessages();

    if (!selectedMap || !pointDraft) {
      setError("Escolhe um ponto na planta primeiro.");
      return;
    }

    setSavingPoint(true);
    try {
      await api.createMapPoint(selectedMap.id, {
        label: pointForm.label?.trim() || null,
        device_type: pointForm.device_type,
        x_percent: pointDraft.x_percent,
        y_percent: pointDraft.y_percent,
      });

      setPointDraft(null);
      await loadMap(selectedMap.id);
      await loadMaps(selectedClientId);
      setSuccess("Ponto criado com sucesso.");
    } catch (e2) {
      setError(e2.message || "Erro ao criar ponto.");
    } finally {
      setSavingPoint(false);
    }
  }

  function openEditPoint(point) {
    setEditingPoint(point);
    setPointDraft(null);
    setPointForm({
      label: point.label || "",
      device_type: point.device_type || "RAT_PVC",
    });
  }

  async function handleUpdatePoint(e) {
    e.preventDefault();
    clearMessages();

    if (!editingPoint) {
      setError("Nenhum ponto selecionado.");
      return;
    }

    setSavingPoint(true);
    try {
      await api.updateMapPoint(editingPoint.id, {
        label: pointForm.label?.trim() || null,
        device_type: pointForm.device_type,
      });

      setEditingPoint(null);
      await loadMap(selectedMap.id);
      await loadMaps(selectedClientId);
      setSuccess("Ponto atualizado com sucesso.");
    } catch (e2) {
      setError(e2.message || "Erro ao editar ponto.");
    } finally {
      setSavingPoint(false);
    }
  }

  async function handleDeletePoint(pointId) {
    if (!pointId) return;
    if (!window.confirm("Apagar este ponto?")) return;

    clearMessages();

    try {
      await api.deleteMapPoint(pointId);
      setEditingPoint(null);
      await loadMap(selectedMap.id);
      await loadMaps(selectedClientId);
      setSuccess("Ponto apagado com sucesso.");
    } catch (e2) {
      setError(e2.message || "Erro ao apagar ponto.");
    }
  }

  function handleVisitCellChange(pointId, field, value) {
    setVisitForm((prev) => ({
      ...prev,
      resultsByPointId: {
        ...prev.resultsByPointId,
        [pointId]: {
          ...(prev.resultsByPointId[pointId] || emptyVisitRow()),
          [field]: value,
        },
      },
    }));
  }

  async function handleCreateVisit(e) {
    e.preventDefault();
    clearMessages();

    if (!selectedClientId || !selectedMap) {
      setError("Escolhe cliente e mapa.");
      return;
    }

    const points = selectedMap.points || [];
    if (points.length === 0) {
      setError("Este mapa ainda não tem pontos.");
      return;
    }

    const results = points.map((p) => {
      const row = visitForm.resultsByPointId[p.id] || emptyVisitRow();

      return {
        site_map_point_id: p.id,
        status_code: row.status_code || null,
        consumption_percent:
          row.consumption_percent === "" || row.consumption_percent == null
            ? null
            : Number(row.consumption_percent),
        action_taken: row.action_taken?.trim() || null,
        notes: row.notes?.trim() || null,
        replaced: Boolean(row.replaced),
      };
    });

    setSavingVisit(true);
    try {
      const created = await api.createMonitoringVisit({
        client_id: Number(selectedClientId),
        pest_type: visitForm.pest_type?.trim() || null,
        notes: visitForm.notes?.trim() || null,
        results,
      });

      await loadVisits(selectedClientId);

      if (created?.id) {
        setSelectedVisitId(String(created.id));
        await api.openMonitoringVisitPdf(created.id);
      }

      resetVisitFormFromMap(selectedMap);
      setSuccess("Visita criada com sucesso.");
    } catch (e2) {
      setError(e2.message || "Erro ao criar visita.");
    } finally {
      setSavingVisit(false);
    }
  }

  async function handleOpenSelectedMapPdf() {
    if (!selectedMap?.id) return;
    clearMessages();
    try {
      await api.openSiteMapPdf(selectedMap.id);
    } catch (e) {
      setError(e.message || "Erro ao abrir PDF do mapa.");
    }
  }

  async function handleOpenVisitPdf(visitId) {
    if (!visitId) return;
    clearMessages();
    try {
      await api.openMonitoringVisitPdf(visitId);
    } catch (e) {
      setError(e.message || "Erro ao abrir PDF da visita.");
    }
  }

  function handleResetVisitForm() {
    resetVisitFormFromMap(selectedMap);
    clearMessages();
  }

  return (
    <div className="monitoringMaps">
      <div className="pageHead">
        <div>
          <h2>Mapas técnicos</h2>
          <p className="muted">
            Cadastro de plantas, pontos de monitorização e geração de relatórios técnicos.
          </p>
        </div>
      </div>

      {error ? <div className="alert alert-error">{error}</div> : null}
      {success ? <div className="alert alert-success">{success}</div> : null}

      <div className="mm-grid">
        <section className="mm-card">
          <h3>1. Cliente</h3>

          <label className="field">
            <span>Selecionar cliente</span>
            <select
              value={selectedClientId}
              onChange={(e) => setSelectedClientId(e.target.value)}
              disabled={loadingClients}
            >
              <option value="">Escolher...</option>
              {clients.map((c) => (
                <option  className="option" key={c.id} value={c.id}>
                  {(c.business_name || c.name || `Cliente ${c.id}`)}
                  {c.client_code ? ` (${c.client_code})` : ""}
                </option>
              ))}
            </select>
          </label>

          {selectedClient ? (
            <div className="clientBox">
              <div>
                <strong>Cliente:</strong> {selectedClient.business_name || selectedClient.name}
              </div>
              <div>
                <strong>Código:</strong> {selectedClient.client_code || selectedClient.id}
              </div>
              <div>
                <strong>Praga:</strong> {selectedClient.pest_type || "—"}
              </div>
              <div>
                <strong>Morada:</strong>{" "}
                {[selectedClient.address, selectedClient.postal_code, selectedClient.city]
                  .filter(Boolean)
                  .join(" ") || "—"}
              </div>
            </div>
          ) : (
            <p className="muted">Escolhe um cliente para começar.</p>
          )}
        </section>

        <section className="mm-card">
          <h3>2. Criar mapa</h3>

          <form onSubmit={handleCreateMap} className="stack">
            <label className="field">
              <span>Nome do mapa</span>
              <input
                value={mapForm.name}
                onChange={(e) => setMapForm((p) => ({ ...p, name: e.target.value }))}
                placeholder="Ex: Piso 0"
                required
              />
            </label>

            <label className="field">
              <span>Ordem</span>
              <input
                type="number"
                min="1"
                value={mapForm.page_order}
                onChange={(e) => setMapForm((p) => ({ ...p, page_order: e.target.value }))}
              />
            </label>

            <label className="field">
              <span>Notas</span>
              <textarea
                rows="3"
                value={mapForm.notes}
                onChange={(e) => setMapForm((p) => ({ ...p, notes: e.target.value }))}
                placeholder="Observações do mapa"
              />
            </label>

            <label className="field">
              <span>Imagem da planta</span>
              <input
                type="file"
                accept=".png,.jpg,.jpeg,.webp"
                onChange={(e) =>
                  setMapForm((p) => ({
                    ...p,
                    image: e.target.files?.[0] || null,
                  }))
                }
              />
            </label>

            <button className="btn" type="submit" disabled={savingMap || !selectedClientId}>
              {savingMap ? "A guardar..." : "Criar mapa"}
            </button>
          </form>
        </section>
      </div>

      <div className="mm-grid mm-grid-3">
        <section className="mm-card">
          <h3>3. Mapas do cliente</h3>

          {loadingMaps ? <p className="muted">A carregar mapas...</p> : null}

          <div className="mapList">
            {maps.map((m) => (
              <button
                type="button"
                key={m.id}
                className={`mapListItem ${String(selectedMapId) === String(m.id) ? "active" : ""}`}
                onClick={() => {
                  setSelectedMapId(String(m.id));
                  setPointDraft(null);
                  setEditingPoint(null);
                }}
              >
                <div className="mapListTitle">{m.name}</div>
                <div className="mapListMeta">
                  Ordem {m.page_order} • {m.points?.length || 0} ponto(s)
                </div>
              </button>
            ))}

            {!loadingMaps && !maps.length ? (
              <p className="muted">Sem mapas para este cliente.</p>
            ) : null}
          </div>

          {selectedMap ? (
            <div className="stack" style={{ marginTop: 12 }}>
              <button
                className="btn btn-secondary"
                type="button"
                onClick={handleOpenSelectedMapPdf}
              >
                Abrir PDF do mapa
              </button>

              <button
                className="btn btn-danger"
                type="button"
                onClick={() => handleDeleteMap(selectedMap.id)}
              >
                Apagar mapa
              </button>
            </div>
          ) : null}
        </section>

        <section className="mm-card mm-card-large">
          <h3>4. Editor da planta</h3>

          {!selectedMap ? (
            <p className="muted">Escolhe um mapa para começar.</p>
          ) : loadingMap ? (
            <p className="muted">A carregar mapa...</p>
          ) : (
            <>
              <p className="muted">
                Clica na imagem para adicionar um ponto. Clica num ponto existente para editar.
              </p>

              <div
                ref={imageWrapRef}
                className="mapCanvas"
                onClick={handleMapClick}
              >
                <img
                    key={selectedMap.image_path}
                    src={`${resolveApiUrl(selectedMap.image_path)}?v=${selectedMap.updated_at || selectedMap.id}`}
                    alt={selectedMap.name}
                    className="mapImage"
                    onError={(e) => {
                      e.currentTarget.style.display = "none";
                      setError(
                        "Imagem da planta não encontrada no servidor. Se isto aconteceu depois do Render reiniciar, precisa de Persistent Disk ou guardar imagens fora do Render."
                      );
                    }}
                    onLoad={(e) => {
                      e.currentTarget.style.display = "block";
                    }}
                />

                {(selectedMap.points || []).map((point) => (
                  <Marker key={point.id} point={point} onClick={openEditPoint} />
                ))}
              </div>
            </>
          )}
        </section>

        <section className="mm-card">
          <h3>5. Ponto</h3>

          {pointDraft ? (
            <form onSubmit={handleCreatePoint} className="stack">
              <div className="clientBox">
                <div><strong>Novo ponto</strong></div>
                <div>X: {pointDraft.x_percent}%</div>
                <div>Y: {pointDraft.y_percent}%</div>
              </div>

              <label className="field">
                <span>Tipo</span>
                <select
                  value={pointForm.device_type}
                  onChange={(e) => setPointForm((p) => ({ ...p, device_type: e.target.value }))}
                >
                  {DEVICE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="field">
                <span>Legenda/local</span>
                <input
                  value={pointForm.label}
                  onChange={(e) => setPointForm((p) => ({ ...p, label: e.target.value }))}
                  placeholder="Ex: Entrada"
                />
              </label>

              <div className="rowBtns">
                <button className="btn" type="submit" disabled={savingPoint}>
                  {savingPoint ? "A guardar..." : "Guardar ponto"}
                </button>
                <button
                  className="btn btn-secondary"
                  type="button"
                  onClick={() => setPointDraft(null)}
                >
                  Cancelar
                </button>
              </div>
            </form>
          ) : editingPoint ? (
            <form onSubmit={handleUpdatePoint} className="stack">
              <div className="clientBox">
                <div><strong>Editar ponto {editingPoint.point_number}</strong></div>
                <div>{deviceLabel(editingPoint.device_type)}</div>
                <div>
                  X: {editingPoint.x_percent}% • Y: {editingPoint.y_percent}%
                </div>
              </div>

              <label className="field">
                <span>Tipo</span>
                <select
                  value={pointForm.device_type}
                  onChange={(e) => setPointForm((p) => ({ ...p, device_type: e.target.value }))}
                >
                  {DEVICE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="field">
                <span>Legenda/local</span>
                <input
                  value={pointForm.label}
                  onChange={(e) => setPointForm((p) => ({ ...p, label: e.target.value }))}
                />
              </label>

              <div className="rowBtns">
                <button className="btn" type="submit" disabled={savingPoint}>
                  {savingPoint ? "A guardar..." : "Salvar"}
                </button>

                <button
                  className="btn btn-danger"
                  type="button"
                  onClick={() => handleDeletePoint(editingPoint.id)}
                >
                  Apagar
                </button>

                <button
                  className="btn btn-secondary"
                  type="button"
                  onClick={() => setEditingPoint(null)}
                >
                  Fechar
                </button>
              </div>
            </form>
          ) : (
            <p className="muted">
              Clica na planta para adicionar um ponto ou num ponto para editar.
            </p>
          )}
        </section>
      </div>

      {selectedMap ? (
        <section className="mm-card" style={{ marginTop: 18 }}>
          <h3>6. Relatório da visita</h3>

          <form onSubmit={handleCreateVisit} className="stack">
            <div className="mm-grid">
              <label className="field">
                <span>Praga</span>
                <input
                  value={visitForm.pest_type}
                  onChange={(e) =>
                    setVisitForm((p) => ({ ...p, pest_type: e.target.value }))
                  }
                  placeholder="Ex: Ratos"
                />
              </label>

              <label className="field">
                <span>Notas gerais</span>
                <textarea
                  rows="3"
                  value={visitForm.notes}
                  onChange={(e) =>
                    setVisitForm((p) => ({ ...p, notes: e.target.value }))
                  }
                  placeholder="Observações gerais da visita"
                />
              </label>
            </div>

            <div className="tableWrap">
              <table className="mm-table">
                <thead>
                  <tr>
                    <th>Ponto</th>
                    <th>Legenda</th>
                    <th>Tipo</th>
                    <th>Estado</th>
                    <th>Consumo %</th>
                    <th>Ação</th>
                    <th>Notas</th>
                    <th>Substituído</th>
                  </tr>
                </thead>
                <tbody>
                  {(selectedMap.points || []).map((p) => {
                    const row = visitForm.resultsByPointId[p.id] || emptyVisitRow();

                    return (
                      <tr key={p.id}>
                        <td>{p.point_number}</td>
                        <td>{p.label || "—"}</td>
                        <td>{deviceLabel(p.device_type)}</td>

                        <td>
                          <select
                            value={row.status_code || "ND"}
                            onChange={(e) =>
                              handleVisitCellChange(p.id, "status_code", e.target.value)
                            }
                          >
                            {STATUS_OPTIONS.map((opt) => (
                              <option key={opt.value} value={opt.value}>
                                {opt.label}
                              </option>
                            ))}
                          </select>
                        </td>

                        <td>
                          <input
                            type="number"
                            min="0"
                            max="100"
                            value={row.consumption_percent ?? ""}
                            onChange={(e) =>
                              handleVisitCellChange(p.id, "consumption_percent", e.target.value)
                            }
                          />
                        </td>

                        <td>
                          <input
                            value={row.action_taken || ""}
                            onChange={(e) =>
                              handleVisitCellChange(p.id, "action_taken", e.target.value)
                            }
                            placeholder="Ex: Reabastecido"
                          />
                        </td>

                        <td>
                          <input
                            value={row.notes || ""}
                            onChange={(e) =>
                              handleVisitCellChange(p.id, "notes", e.target.value)
                            }
                            placeholder="Notas"
                          />
                        </td>

                        <td>
                          <input
                            type="checkbox"
                            checked={Boolean(row.replaced)}
                            onChange={(e) =>
                              handleVisitCellChange(p.id, "replaced", e.target.checked)
                            }
                          />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="rowBtns">
              <button className="btn" type="submit" disabled={savingVisit}>
                {savingVisit ? "A guardar..." : "Guardar visita e abrir PDF"}
              </button>

              <button
                className="btn btn-secondary"
                type="button"
                onClick={handleResetVisitForm}
              >
                Limpar formulário
              </button>
            </div>
          </form>
        </section>
      ) : null}

      {selectedClientId ? (
        <section className="mm-card" style={{ marginTop: 18 }}>
          <h3>7. Visitas já criadas</h3>

          {loadingVisits ? (
            <p className="muted">A carregar visitas...</p>
          ) : visits.length === 0 ? (
            <p className="muted">Ainda não existem visitas para este cliente.</p>
          ) : (
            <div className="tableWrap">
              <table className="mm-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Data</th>
                    <th>Praga</th>
                    <th>Notas</th>
                    <th>Resultados</th>
                    <th>Ações</th>
                  </tr>
                </thead>
                <tbody>
                  {visits.map((v) => (
                    <tr key={v.id}>
                      <td>{v.id}</td>
                      <td>
                        {v.visit_date
                          ? new Date(v.visit_date).toLocaleString("pt-PT")
                          : "—"}
                      </td>
                      <td>{v.pest_type || "—"}</td>
                      <td>{v.notes || "—"}</td>
                      <td>{Array.isArray(v.results) ? v.results.length : 0}</td>
                      <td>
                        <div className="rowBtns">
                          <button
                            type="button"
                            className="btn btn-secondary"
                            onClick={() => {
                              setSelectedVisitId(String(v.id));
                              handleOpenVisitPdf(v.id);
                            }}
                          >
                            Abrir PDF
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {selectedVisitId ? (
            <p className="muted" style={{ marginTop: 12 }}>
              Última visita selecionada: #{selectedVisitId}
            </p>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}