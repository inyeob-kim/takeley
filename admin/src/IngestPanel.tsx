import { useEffect, useState, type ReactNode } from "react";
import {
  createRssFeed,
  deleteRssFeed,
  fetchDiscoveryModules,
  fetchIndustrySearch,
  fetchPipelineControls,
  fetchRssFeeds,
  fetchXIngestConfig,
  fetchXIngestStats,
  saveDiscoveryModules,
  saveIndustrySearch,
  savePipelineControls,
  saveXIngestConfig,
  updateRssFeed,
  type AdminRssFeed,
  type DiscoveryModule,
  type IndustrySearch,
  type PipelineControls,
  type XIngestConfig,
  type XIngestStats,
} from "./api";
import { ConfirmModal } from "./ConfirmModal";
import {
  doneThroughMinutes,
  formatHm,
  kstNow,
  laneText,
  parseScanHours,
  phaseLabel,
  slotPhase,
  slotStatName,
  windowLabel,
  type ClockSlot,
} from "./ingestSchedule";

type Props = {
  adminKey: string;
  onAuthFailure?: () => void;
};

const INDUSTRY_OPTIONS = [
  ["politics", "정치"],
  ["economy", "경제"],
  ["finance", "금융"],
  ["tech", "기술"],
  ["ai", "AI"],
  ["society", "사회"],
  ["world", "국제"],
  ["culture", "문화"],
  ["sports", "스포츠"],
  ["entertainment", "엔터"],
] as const;

const INDUSTRY_LABEL = Object.fromEntries(INDUSTRY_OPTIONS);

const MODULE_LABEL: Record<string, string> = {
  x: "X",
  rss: "RSS",
  trends: "Search Trends",
  reddit: "Reddit",
  hacker_news: "Hacker News",
  official: "Official",
};

const MODULE_HINT: Record<string, string> = {
  x: "계정·검색. 아래 X 탭에서 시각을 정합니다.",
  rss: "관리하는 공개 피드. 과금 없습니다.",
  trends: "Google Trends KR/US. 스포츠·연예는 걸러집니다.",
  reddit: "승인 전에는 꺼 두세요.",
  hacker_news: "공개 상위 스토리.",
  official: "SEC 주요 공시. DART는 키가 있을 때만.",
};

const STATUS_LABEL: Record<string, string> = {
  ok: "정상",
  error: "오류",
  skipped: "건너뜀",
  running: "실행 중",
};

type IngestTab = "sources" | "rss" | "x" | "process" | "stats";

function formatAgo(iso: string | null | undefined): string {
  if (!iso) return "아직 없음";
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return iso;
  const minutes = Math.round((Date.now() - at.getTime()) / 60_000);
  if (minutes < 1) return "방금";
  if (minutes < 60) return `${minutes}분 전`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}시간 전`;
  return at.toLocaleString("ko-KR", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function intervalLabel(seconds: number | null | undefined): string {
  if (!seconds || seconds <= 0) return "매 주기";
  if (seconds < 3600) return `${Math.round(seconds / 60)}분마다`;
  if (seconds % 3600 === 0) return `${seconds / 3600}시간마다`;
  return `${Math.round(seconds / 60)}분마다`;
}

export function IngestPanel({ adminKey, onAuthFailure }: Props) {
  const [form, setForm] = useState<XIngestConfig | null>(null);
  const [industries, setIndustries] = useState<IndustrySearch[]>([]);
  const [stats, setStats] = useState<XIngestStats | null>(null);
  const [days, setDays] = useState(7);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [now, setNow] = useState(() => new Date());
  const [openIndustry, setOpenIndustry] = useState<string | null>(null);
  const [modules, setModules] = useState<DiscoveryModule[]>([]);
  const [pipeline, setPipeline] = useState<PipelineControls | null>(null);
  const [feeds, setFeeds] = useState<AdminRssFeed[]>([]);
  const [newFeedName, setNewFeedName] = useState("");
  const [newFeedUrl, setNewFeedUrl] = useState("");
  const [tab, setTab] = useState<IngestTab>("sources");

  async function load(nextDays = days) {
    try {
      const [config, report, words, sourceModules, pipe, rss] = await Promise.all([
        fetchXIngestConfig(adminKey),
        fetchXIngestStats(adminKey, nextDays),
        fetchIndustrySearch(adminKey),
        fetchDiscoveryModules(adminKey),
        fetchPipelineControls(adminKey),
        fetchRssFeeds(adminKey),
      ]);
      setForm(config);
      setStats(report);
      setIndustries(words.map(presentIndustry));
      setModules(sourceModules);
      setPipeline(pipe);
      setFeeds(rss);
      setError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : "불러오지 못했습니다";
      if (message.includes("401") || message.includes("403")) onAuthFailure?.();
      setError(message);
    }
  }

  useEffect(() => {
    void load(days);
  }, [adminKey, days]);

  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 30_000);
    return () => window.clearInterval(id);
  }, []);

  function patch(partial: Partial<XIngestConfig>) {
    setForm((prev) => (prev ? { ...prev, ...partial } : prev));
  }

  function patchIndustry(key: string, partial: Partial<IndustrySearch>) {
    setIndustries((prev) =>
      prev.map((row) => (row.industry_key === key ? { ...row, ...partial } : row)),
    );
  }

  function toggleIndustry(key: string) {
    if (!form) return;
    const current = form.industries
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    const next = current.includes(key)
      ? current.filter((item) => item !== key)
      : [...current, key];
    patch({ industries: next.join(",") });
  }

  async function save() {
    if (!form) return;
    setBusy(true);
    setNotice(null);
    try {
      const saved = await saveXIngestConfig(adminKey, form);
      if (modules.length) {
        setModules(
          await saveDiscoveryModules(
            adminKey,
            modules.map((row) => ({
              id: row.id,
              enabled: row.enabled,
              interval_seconds: row.interval_seconds,
            })),
          ),
        );
      }
      if (pipeline) {
        setPipeline(await savePipelineControls(adminKey, pipeline));
      }
      const savedWords = await saveIndustrySearch(
        adminKey,
        industries.map((row) => ({
          ...row,
          enabled: form.industries
            .split(",")
            .map((item) => item.trim())
            .includes(row.industry_key),
        })),
      );
      setForm(saved);
      setIndustries(savedWords.map(presentIndustry));
      setNotice("저장했습니다. 이미 켜 둔 워커는 다음 확인 때부터 이 값을 읽습니다.");
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "저장하지 못했습니다");
    } finally {
      setBusy(false);
    }
  }

  if (!form) {
    return <p className="ingest-status">{error || "불러오는 중"}</p>;
  }

  const selected = new Set(
    form.industries
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean),
  );
  const scheduled = form.scan_mode === "scheduled";
  const slots = parseScanHours(form.scan_hours_kst);
  const lanes = [form.morning_lane, form.afternoon_lane, form.night_lane];
  const morningWhen = windowLabel(slots[0], form.scan_window_minutes);
  const accountNight = windowLabel(slots[slots.length - 1], form.scan_window_minutes);
  const allWhen = slots.map((slot) => formatHm(slot.hour, slot.minute)).join(", ");
  const onCount = modules.filter((row) => row.enabled).length;
  const errorCount = modules.filter((row) => row.last_status === "error").length;
  const rssOn = modules.some((row) => row.id === "rss" && row.enabled);

  return (
    <section className="ingest-panel">
      <header className="ingest-head">
        <div>
          <h2>수집</h2>
          <p>
            소스만 켜고 끄면 됩니다. X 시각·검색어는 X 탭, 피드는 RSS 탭입니다.
          </p>
        </div>
        <button
          type="button"
          className="primary"
          onClick={() => void save()}
          disabled={busy}
        >
          {busy ? "저장 중" : "저장"}
        </button>
      </header>
      {notice ? <p className="ingest-notice">{notice}</p> : null}
      {error ? <p className="ingest-error">{error}</p> : null}

      <nav className="section-nav ingest-tabs" aria-label="수집 구역">
        {(
          [
            ["sources", `소스 ${onCount}/${modules.length}`],
            ["rss", `RSS ${feeds.length}`],
            ["x", "X"],
            ["process", "처리"],
            ["stats", "실적"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={tab === id ? "is-active" : undefined}
            onClick={() => setTab(id)}
          >
            {label}
            {id === "sources" && errorCount ? (
              <span className="ingest-tab-warn">오류 {errorCount}</span>
            ) : null}
          </button>
        ))}
      </nav>

      {tab === "sources" ? (
        <section className="ingest-block ingest-block--flush">
          <p className="ingest-lead">
            꺼 두면 그 소스의 신규 수집만 멈춥니다. 이미 만든 이슈는 그대로입니다.
          </p>
          <div className="source-grid">
            {modules.map((row) => (
              <article
                key={row.id}
                className={
                  row.enabled ? "source-card" : "source-card is-off"
                }
              >
                <div className="source-card__top">
                  <label className="ingest-switch source-card__switch">
                    <input
                      type="checkbox"
                      checked={row.enabled}
                      disabled={!row.implemented}
                      onChange={(event) =>
                        setModules((prev) =>
                          prev.map((item) =>
                            item.id === row.id
                              ? { ...item, enabled: event.target.checked }
                              : item,
                          ),
                        )
                      }
                    />
                    <span>
                      <strong>{MODULE_LABEL[row.id] || row.id}</strong>
                      <small>{MODULE_HINT[row.id] || ""}</small>
                    </span>
                  </label>
                  <span
                    className={`source-chip is-${row.last_status || "idle"}`}
                  >
                    {!row.implemented
                      ? "준비 중"
                      : STATUS_LABEL[row.last_status || ""] || "대기"}
                  </span>
                </div>
                <p className="source-card__meta">
                  {intervalLabel(row.interval_seconds)}
                  {" · "}
                  {formatAgo(row.last_finished_at)}
                  {row.implemented
                    ? ` · 가져옴 ${row.items_fetched} · 저장 ${row.items_inserted}`
                    : ""}
                </p>
                {row.id !== "x" && row.implemented ? (
                  <label className="source-card__interval">
                    <span>간격</span>
                    <select
                      value={String(row.interval_seconds || 3600)}
                      onChange={(event) =>
                        setModules((prev) =>
                          prev.map((item) =>
                            item.id === row.id
                              ? {
                                  ...item,
                                  interval_seconds: Number(event.target.value),
                                }
                              : item,
                          ),
                        )
                      }
                    >
                      <option value="1800">30분</option>
                      <option value="3600">1시간</option>
                      <option value="7200">2시간</option>
                    </select>
                  </label>
                ) : null}
                {row.last_error ? (
                  <p className="source-card__error">{row.last_error}</p>
                ) : null}
                {row.id === "rss" ? (
                  <button
                    type="button"
                    className="source-card__link"
                    onClick={() => setTab("rss")}
                  >
                    피드 {feeds.length}개 관리
                  </button>
                ) : null}
                {row.id === "x" ? (
                  <button
                    type="button"
                    className="source-card__link"
                    onClick={() => setTab("x")}
                  >
                    시각·검색어 설정
                  </button>
                ) : null}
              </article>
            ))}
          </div>
        </section>
      ) : null}

      {tab === "rss" ? (
        <RssFeedsBlock
          adminKey={adminKey}
          feeds={feeds}
          rssOn={rssOn}
          newName={newFeedName}
          newUrl={newFeedUrl}
          onName={setNewFeedName}
          onUrl={setNewFeedUrl}
          onChange={setFeeds}
          onError={setError}
        />
      ) : null}

      {tab === "process" && pipeline ? (
        <section className="ingest-block ingest-block--flush">
          <h3>처리 단계</h3>
          <p className="ingest-lead">
            수집과 따로입니다. 끄면 다음 주기부터 그 단계만 건너뜁니다.
          </p>
          {(
            [
              ["process_enabled", "초안", "이슈 초안 만들기"],
              ["trend_enabled", "급상승", "발행된 이슈의 급상승 갱신"],
              ["push_enabled", "알림", "대기 중인 알림 보내기"],
            ] as const
          ).map(([key, title, hint]) => (
            <label className="ingest-switch" key={key}>
              <input
                type="checkbox"
                checked={pipeline[key]}
                onChange={(event) =>
                  setPipeline((prev) =>
                    prev ? { ...prev, [key]: event.target.checked } : prev,
                  )
                }
              />
              <span>
                <strong>{title}</strong>
                <small>{hint}</small>
              </span>
            </label>
          ))}
        </section>
      ) : null}

      {tab === "x" ? (
      <>
      <DayClock
        scheduled={scheduled}
        slots={slots}
        lanes={lanes}
        windowMinutes={form.scan_window_minutes}
        hotEnabled={form.hot_enabled}
        hotMinutes={form.hot_interval_minutes}
        now={now}
        lastSlotKey={stats?.last_slot_key ?? null}
        onLane={(index, value) => {
          if (index <= 0) patch({ morning_lane: value });
          else if (index === 1) patch({ afternoon_lane: value });
          else patch({ night_lane: value });
        }}
      />

      <section className="ingest-block">
        <h3>시각</h3>
        <p className="ingest-lead">
          위 시간표의 색 구간에서만 X를 한 번 부릅니다. 언어는 각 시각 카드에서
          고릅니다.
        </p>
        <div className="ingest-settings">
          <Setting title="수집 방식">
            <select
              value={form.scan_mode}
              onChange={(event) => patch({ scan_mode: event.target.value })}
            >
              <option value="scheduled">정한 시각만</option>
              <option value="interval">30분마다 계속</option>
            </select>
          </Setting>
          <Setting
            title="시각"
            hint="한국 시간, 쉼표로 구분. 예: 06:30,16:00,22:30"
          >
            <input
              value={form.scan_hours_kst}
              onChange={(event) => patch({ scan_hours_kst: event.target.value })}
              disabled={!scheduled}
            />
          </Setting>
          <Setting
            title="여유 분"
            hint="이 분 안에 깨어나면 그 시각을 놓치지 않습니다."
          >
            <input
              type="number"
              value={form.scan_window_minutes}
              onChange={(event) =>
                patch({ scan_window_minutes: Number(event.target.value) })
              }
              disabled={!scheduled}
            />
          </Setting>
        </div>
      </section>

      <section className="ingest-block">
        <h3>산업</h3>
        <p className="ingest-lead">
          켜 둔 산업만 검색합니다. 높음은 반대 언어도 조금 보고, 간격이 긴
          산업은 매번 보지 않습니다. 이름을 누르면 검색어가 열립니다.
        </p>
        <div className="industry-list">
          {industries.map((row) => (
            <IndustryRow
              key={row.industry_key}
              row={row}
              on={selected.has(row.industry_key)}
              open={openIndustry === row.industry_key}
              onToggle={() => toggleIndustry(row.industry_key)}
              onOpen={() =>
                setOpenIndustry((current) =>
                  current === row.industry_key ? null : row.industry_key,
                )
              }
              onChange={(partial) => patchIndustry(row.industry_key, partial)}
            />
          ))}
        </div>
      </section>

      <section className="ingest-block">
        <h3>계정</h3>
        <p className="ingest-lead">
          검색어 없이 계정 타임라인만 가져옵니다. 목록에서 자동으로 빠지지
          않습니다.
        </p>
        <div className="ingest-settings">
          <Setting title="계정" wide>
            <input
              value={form.track_accounts}
              onChange={(event) => patch({ track_accounts: event.target.value })}
              placeholder="DeItaone, StockMKTNewz, FirstSquawk"
            />
          </Setting>
          <Setting title="언제">
            <select
              value={form.accounts_on}
              onChange={(event) => patch({ accounts_on: event.target.value })}
            >
              <option value="off">가져오지 않음</option>
              <option value="morning">
                {morningWhen ? `${morningWhen}만` : "첫 시각만"}
              </option>
              <option value="night">
                {accountNight ? `${accountNight}만` : "마지막 시각만"}
              </option>
              <option value="all">
                {allWhen ? `모든 시각 (${allWhen})` : "매 시각"}
              </option>
            </select>
          </Setting>
        </div>
      </section>

      <section className="ingest-block">
        <h3>양</h3>
        <p className="ingest-lead">
          한 시각에 너무 많이 읽지 않게 막는 숫자입니다. 하루 상한을 넘기면
          그날의 추가 검색만 건너뜁니다.
        </p>
        <div className="ingest-settings">
          <Setting title="한 시각 산업 수">
            <input
              type="number"
              value={form.lanes_per_scan}
              onChange={(event) =>
                patch({ lanes_per_scan: Number(event.target.value) })
              }
            />
          </Setting>
          <Setting title="산업당 글 수">
            <input
              type="number"
              value={form.max_results}
              onChange={(event) =>
                patch({ max_results: Number(event.target.value) })
              }
            />
          </Setting>
          <Setting title="반대 언어" hint="높은 산업만, 이 개수만큼.">
            <input
              type="number"
              value={form.opposite_lane_count}
              onChange={(event) =>
                patch({ opposite_lane_count: Number(event.target.value) })
              }
            />
          </Setting>
          <Setting title="하루 글 상한">
            <input
              type="number"
              value={form.daily_post_budget}
              onChange={(event) =>
                patch({ daily_post_budget: Number(event.target.value) })
              }
            />
          </Setting>
          <Setting
            title="따라가는 검색"
            hint="이미 만든 이슈에서 나온 짧은 추가 검색입니다."
          >
            <select
              value={form.dynamic_mode}
              onChange={(event) => patch({ dynamic_mode: event.target.value })}
            >
              <option value="off">끄기</option>
              <option value="hot">급등할 때만</option>
              <option value="normal">일반 수집에도</option>
            </select>
          </Setting>
        </div>
      </section>

      <section className="ingest-block">
        <h3>급등</h3>
        <p className="ingest-lead">
          답글이 기준을 넘으면 그 산업만 색 구간 밖에서도 다시 봅니다. 새
          이슈도 없고 근거도 안 바뀌면 멈춥니다.
        </p>
        <label className="ingest-switch">
          <input
            type="checkbox"
            checked={form.hot_enabled}
            onChange={(event) => patch({ hot_enabled: event.target.checked })}
          />
          <span>
            <strong>추가 감시</strong>
            <small>끄면 다음 정규 시각까지 기다립니다.</small>
          </span>
        </label>
        {form.hot_enabled ? <div className="ingest-settings">
          <Setting
            title="다시 보는 간격"
            hint="감시 중인 산업을 이 분마다 한 번 더 가져옵니다."
          >
            <input
              type="number"
              value={form.hot_interval_minutes}
              onChange={(event) =>
                patch({ hot_interval_minutes: Number(event.target.value) })
              }
            />
          </Setting>
          <Setting
            title="조용하면 끊는 횟수"
            hint="새 이슈도 없고 기존 이슈 근거도 그대로인 확인이 이 횟수면 감시를 끝냅니다. 글을 못 가져온 것과는 다릅니다."
          >
            <input
              type="number"
              value={form.hot_idle_scans}
              onChange={(event) =>
                patch({ hot_idle_scans: Number(event.target.value) })
              }
            />
          </Setting>
          <Setting
            title="최대 감시 시간"
            hint="결과가 있어도 이 시간이 지나면 감시를 끝냅니다."
          >
            <input
              type="number"
              value={form.hot_max_hours}
              onChange={(event) =>
                patch({ hot_max_hours: Number(event.target.value) })
              }
            />
          </Setting>
          <Setting
            title="답글 기준"
            hint="한 글의 답글이 이 수 이상이면 그 산업을 감시에 올립니다."
          >
            <input
              type="number"
              value={form.hot_reply_spike}
              onChange={(event) =>
                patch({ hot_reply_spike: Number(event.target.value) })
              }
            />
          </Setting>
        </div> : null}
      </section>
      </>
      ) : null}

      {tab === "process" ? (
      <section className="ingest-block">
        <h3>분석과 단가</h3>
        <p className="ingest-lead">
          AI는 가져온 글 전부가 아니라 예산 안의 글만 읽습니다. 단가는 이
          화면의 예상 비용 계산에 씁니다.
        </p>
        <label className="ingest-switch">
          <input
            type="checkbox"
            checked={form.industry_slot_reserve}
            onChange={(event) =>
              patch({ industry_slot_reserve: event.target.checked })
            }
          />
          <span>
            <strong>산업마다 분석 자리 하나</strong>
            <small>
              켜면 문화·스포츠처럼 반응이 적은 산업도 예산 안에서 최소 한
              글은 읽습니다.
            </small>
          </span>
        </label>
        <div className="ingest-settings">
          <Setting
            title="한 번에 읽을 글"
            hint="워커 한 주기에 AI가 이슈로 판단할 글 수입니다."
          >
            <input
              type="number"
              value={form.understand_budget}
              onChange={(event) =>
                patch({ understand_budget: Number(event.target.value) })
              }
            />
          </Setting>
          <Setting
            title="글 하나당 달러"
            hint="X가 돌려준 게시물 1건의 단가입니다. 공개 종량제는 0.005달러입니다."
          >
            <input
              type="number"
              step="0.001"
              value={form.usd_per_post}
              onChange={(event) =>
                patch({ usd_per_post: Number(event.target.value) })
              }
            />
          </Setting>
          <Setting
            title="계정 조회당 달러"
            hint="사용자 정보를 한 번 읽을 때의 단가입니다. 공개 종량제는 0.01달러입니다."
          >
            <input
              type="number"
              step="0.001"
              value={form.usd_per_user}
              onChange={(event) =>
                patch({ usd_per_user: Number(event.target.value) })
              }
            />
          </Setting>
        </div>
      </section>
      ) : null}

      {tab === "stats" ? (
      <StatsBlock
        stats={stats}
        days={days}
        onDays={setDays}
        industryLabel={INDUSTRY_LABEL}
      />
      ) : null}

      <div className="ingest-savebar">
        <p>{notice || "소스·X·처리 설정은 저장해야 반영됩니다. RSS 피드는 바로 저장됩니다."}</p>
        <button
          type="button"
          className="primary"
          onClick={() => void save()}
          disabled={busy}
        >
          {busy ? "저장 중" : "저장"}
        </button>
      </div>
    </section>
  );
}

function asCommaList(value: string) {
  return value
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean)
    .join(", ");
}

function presentIndustry(row: IndustrySearch): IndustrySearch {
  return {
    ...row,
    keywords_ko: asCommaList(row.keywords_ko),
    keywords_en: asCommaList(row.keywords_en),
    exclude_ko: asCommaList(row.exclude_ko),
    exclude_en: asCommaList(row.exclude_en),
  };
}

function wordCount(value: string) {
  return value
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean).length;
}

function RssFeedsBlock({
  adminKey,
  feeds,
  rssOn,
  newName,
  newUrl,
  onName,
  onUrl,
  onChange,
  onError,
}: {
  adminKey: string;
  feeds: AdminRssFeed[];
  rssOn: boolean;
  newName: string;
  newUrl: string;
  onName: (value: string) => void;
  onUrl: (value: string) => void;
  onChange: (feeds: AdminRssFeed[]) => void;
  onError: (message: string | null) => void;
}) {
  const [pendingDelete, setPendingDelete] = useState<AdminRssFeed | null>(null);
  const [busy, setBusy] = useState(false);

  async function addFeed() {
    if (!newUrl.trim()) {
      onError("피드 주소를 넣어 주세요.");
      return;
    }
    setBusy(true);
    try {
      const created = await createRssFeed(adminKey, {
        name: newName,
        url: newUrl,
        enabled: true,
      });
      onChange([...feeds, created]);
      onName("");
      onUrl("");
      onError(null);
    } catch (err) {
      onError(err instanceof Error ? err.message : "피드를 추가하지 못했어요.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="ingest-block ingest-block--flush">
      <h3>RSS 피드</h3>
      <p className="ingest-lead">
        {rssOn
          ? "켜 둔 피드만 1시간마다 받습니다. 추가·켜기·삭제는 바로 저장됩니다."
          : "피드 목록은 여기서 관리합니다. 소스 탭에서 RSS를 켜야 받아옵니다."}
      </p>
      <div className="ingest-settings">
        <Setting title="이름">
          <input
            value={newName}
            onChange={(event) => onName(event.target.value)}
            placeholder="연합뉴스"
          />
        </Setting>
        <Setting title="주소" hint="http:// 또는 https:// RSS/Atom" wide>
          <input
            value={newUrl}
            onChange={(event) => onUrl(event.target.value)}
            placeholder="https://feeds.bbci.co.uk/news/rss.xml"
          />
        </Setting>
      </div>
      <p>
        <button
          type="button"
          className="primary"
          disabled={busy}
          onClick={() => void addFeed()}
        >
          {busy ? "추가 중" : "피드 추가"}
        </button>
      </p>
      {feeds.length === 0 ? (
        <p className="ingest-status">등록된 피드가 없습니다.</p>
      ) : (
        <ul className="feed-list">
          {feeds.map((feed) => (
            <li key={feed.id} className={feed.enabled ? "feed-row" : "feed-row is-off"}>
              <label className="feed-row__on">
                <input
                  type="checkbox"
                  checked={feed.enabled}
                  onChange={(event) => {
                    const enabled = event.target.checked;
                    void updateRssFeed(adminKey, feed.id, { enabled })
                      .then((saved) =>
                        onChange(
                          feeds.map((item) =>
                            item.id === feed.id ? saved : item,
                          ),
                        ),
                      )
                      .catch((err) =>
                        onError(
                          err instanceof Error
                            ? err.message
                            : "피드를 바꾸지 못했어요.",
                        ),
                      );
                  }}
                />
                <span>{feed.enabled ? "켬" : "끔"}</span>
              </label>
              <div className="feed-row__body">
                <strong>{feed.name}</strong>
                <small>{feed.url}</small>
                <span>
                  {feed.last_error
                    ? feed.last_error
                    : `최근 성공 ${formatAgo(feed.last_success_at)}`}
                </span>
              </div>
              <button
                type="button"
                className="feed-row__delete"
                onClick={() => setPendingDelete(feed)}
              >
                삭제
              </button>
            </li>
          ))}
        </ul>
      )}
      <ConfirmModal
        open={pendingDelete !== null}
        title="이 피드를 삭제할까요?"
        body={pendingDelete ? pendingDelete.name : undefined}
        confirmLabel="삭제"
        tone="danger"
        onCancel={() => setPendingDelete(null)}
        onConfirm={() => {
          const feed = pendingDelete;
          if (!feed) return;
          void deleteRssFeed(adminKey, feed.id)
            .then(() => {
              onChange(feeds.filter((item) => item.id !== feed.id));
              setPendingDelete(null);
            })
            .catch((err) =>
              onError(
                err instanceof Error ? err.message : "피드를 지우지 못했어요.",
              ),
            );
        }}
      />
    </section>
  );
}

function IndustryRow({
  row,
  on,
  open,
  onToggle,
  onOpen,
  onChange,
}: {
  row: IndustrySearch;
  on: boolean;
  open: boolean;
  onToggle: () => void;
  onOpen: () => void;
  onChange: (partial: Partial<IndustrySearch>) => void;
}) {
  const words = wordCount(row.keywords_ko) + wordCount(row.keywords_en);
  return (
    <article className={on ? "industry-row" : "industry-row is-off"}>
      <div className="industry-row__bar">
        <label className="industry-toggle">
          <input type="checkbox" checked={on} onChange={onToggle} />
          <span>{on ? "켬" : "끔"}</span>
        </label>
        <button type="button" className="industry-row__name" onClick={onOpen}>
          <strong>{row.label}</strong>
          <small>
            {words}개 검색어
            {open ? " · 접기" : " · 검색어"}
          </small>
        </button>
        <select
          aria-label={`${row.label} 간격`}
          value={row.frequency}
          onChange={(event) => onChange({ frequency: event.target.value })}
        >
          <option value="every_scan">매 시각</option>
          <option value="every_2">2번에 한 번</option>
          <option value="every_3">3번에 한 번</option>
        </select>
        <select
          aria-label={`${row.label} 중요도`}
          value={row.priority}
          onChange={(event) => onChange({ priority: event.target.value })}
        >
          <option value="high">높음</option>
          <option value="normal">보통</option>
          <option value="low">낮음</option>
        </select>
      </div>
      {open ? (
        <div className="industry-row__edit">
          <p>쉼표로 구분합니다. OR, lang, 괄호는 넣지 않습니다.</p>
          <Setting title="한국어" wide>
            <input
              value={row.keywords_ko}
              placeholder="대통령, 국회, 정부"
              onChange={(event) => onChange({ keywords_ko: event.target.value })}
            />
          </Setting>
          <Setting title="영어" wide>
            <input
              value={row.keywords_en}
              placeholder="Trump, election, Congress"
              onChange={(event) => onChange({ keywords_en: event.target.value })}
            />
          </Setting>
          <Setting title="빼는 말 · 한국어">
            <input
              value={row.exclude_ko}
              placeholder="예능, 광고"
              onChange={(event) => onChange({ exclude_ko: event.target.value })}
            />
          </Setting>
          <Setting title="빼는 말 · 영어">
            <input
              value={row.exclude_en}
              placeholder="meme, giveaway"
              onChange={(event) => onChange({ exclude_en: event.target.value })}
            />
          </Setting>
        </div>
      ) : null}
    </article>
  );
}

function Setting({
  title,
  hint,
  wide = false,
  children,
}: {
  title: string;
  hint?: string;
  wide?: boolean;
  children: ReactNode;
}) {
  return (
    <label className={wide ? "ingest-setting ingest-setting--wide" : "ingest-setting"}>
      <span className="ingest-setting__title">{title}</span>
      {children}
      {hint ? <small>{hint}</small> : null}
    </label>
  );
}

function LaneSelect({
  value,
  onChange,
  allowAuto,
}: {
  value: string;
  onChange: (value: string) => void;
  allowAuto: boolean;
}) {
  return (
    <select value={value} onChange={(event) => onChange(event.target.value)}>
      {allowAuto ? <option value="auto">분석이 적은 쪽</option> : null}
      <option value="korea">한국</option>
      <option value="global">글로벌</option>
    </select>
  );
}

function DayClock({
  scheduled,
  slots,
  lanes,
  windowMinutes,
  hotEnabled,
  hotMinutes,
  now,
  lastSlotKey,
  onLane,
}: {
  scheduled: boolean;
  slots: ClockSlot[];
  lanes: string[];
  windowMinutes: number;
  hotEnabled: boolean;
  hotMinutes: number;
  now: Date;
  lastSlotKey: string | null;
  onLane: (index: number, value: string) => void;
}) {
  const clock = kstNow(now);
  const doneThrough = doneThroughMinutes(lastSlotKey, clock.dateKey);
  const nowPct = (clock.minutes / 1440) * 100;

  return (
    <section className="ingest-block ingest-clock">
      <header className="ingest-clock__head">
        <h3>오늘 시간표</h3>
        <p>한국 시간 {clock.label}</p>
      </header>
      {scheduled && slots.length === 0 ? (
        <p className="ingest-lead">
          시각 형식이 비어 있거나 잘못되었습니다. 06:30,16:00,22:30처럼
          적어 주세요.
        </p>
      ) : scheduled ? (
        <>
          <div className="day-ruler" aria-hidden="true">
            <div className="day-ruler__ticks" />
            {slots.map((slot) => {
              const phase = slotPhase(slot, windowMinutes, clock.minutes, doneThrough);
              const left = (slot.startMin / 1440) * 100;
              const width = Math.max((windowMinutes / 1440) * 100, 1.8);
              return (
                <span
                  key={slot.index}
                  className={`day-window is-${phase}`}
                  style={{ left: `${left}%`, width: `${width}%` }}
                  title={`${slot.title} ${formatHm(slot.hour, slot.minute)}`}
                />
              );
            })}
            <span className="day-now" style={{ left: `${nowPct}%` }} />
          </div>
          <div className="day-hours">
            <span>0시</span>
            <span>6시</span>
            <span>12시</span>
            <span>18시</span>
            <span>24시</span>
          </div>
          <p className="ingest-legend">
            색 구간 안에서 한 번만 가져옵니다.
            {hotEnabled ? ` 급등 산업은 ${hotMinutes}분마다 더 봅니다.` : ""}
          </p>
          <ol className="day-cards">
            {slots.map((slot) => {
              const phase = slotPhase(
                slot,
                windowMinutes,
                clock.minutes,
                doneThrough,
              );
              const endMin = slot.startMin + windowMinutes;
              const endH = Math.floor(endMin / 60) % 24;
              const endM = endMin % 60;
              const laneIndex = Math.min(slot.index, 2);
              const lane = lanes[laneIndex] ?? "global";
              return (
                <li key={slot.index} className={`is-${phase}`}>
                  <span className="day-cards__phase">{phaseLabel(phase)}</span>
                  <strong>
                    {slot.title} {formatHm(slot.hour, slot.minute)}–
                    {formatHm(endH, endM)}
                  </strong>
                  <LaneSelect
                    value={lane}
                    allowAuto={laneIndex >= 2}
                    onChange={(value) => onLane(laneIndex, value)}
                  />
                </li>
              );
            })}
          </ol>
        </>
      ) : (
        <p className="ingest-lead">
          지금은 30분마다 X를 계속 가져옵니다. 위의 색 시간표는 하루 몇 번으로
          바꾸면 적용됩니다.
        </p>
      )}
    </section>
  );
}

function StatsBlock({
  stats,
  days,
  onDays,
  industryLabel,
}: {
  stats: XIngestStats | null;
  days: number;
  onDays: (days: number) => void;
  industryLabel: Record<string, string>;
}) {
  return (
    <section className="ingest-block">
      <header className="ingest-head">
        <div>
          <h3>최근 실적</h3>
          <p>예상 비용은 위에서 저장한 단가 × 가져온 글 수입니다.</p>
        </div>
        <select
          value={days}
          onChange={(event) => onDays(Number(event.target.value))}
          aria-label="실적 기간"
        >
          <option value={1}>1일</option>
          <option value={7}>7일</option>
          <option value={30}>30일</option>
        </select>
      </header>
      {stats ? (
        <>
          <dl className="ingest-metrics">
            <div>
              <dt>예상 비용</dt>
              <dd>${stats.estimated_usd.toFixed(2)}</dd>
            </div>
            <div>
              <dt>이슈 하나당</dt>
              <dd>
                {stats.usd_per_new_issue == null
                  ? "—"
                  : `$${stats.usd_per_new_issue.toFixed(2)}`}
              </dd>
            </div>
            <div>
              <dt>가져온 글</dt>
              <dd>{stats.posts_fetched}</dd>
            </div>
            <div>
              <dt>새 이슈</dt>
              <dd>{stats.new_issues}</dd>
            </div>
          </dl>
          <p className="ingest-legend">
            한국어 {stats.korea_posts} · 영어 {stats.global_posts} · 갱신{" "}
            {stats.updates} · 검색 {stats.search_calls}회 · 계정{" "}
            {stats.timeline_calls}회 · 추가 검색 {stats.dynamic_queries} · 급등{" "}
            {stats.hot_scans}
          </p>
          {stats.slots.length ? (
            <table className="ingest-table">
              <caption>시각별 비용. 예전 기록은 아침/오후/밤 표시가 없습니다.</caption>
              <thead>
                <tr>
                  <th>구분</th>
                  <th>글</th>
                  <th>이슈</th>
                  <th>예상 비용</th>
                  <th>이슈당</th>
                </tr>
              </thead>
              <tbody>
                {stats.slots.map((row) => (
                  <tr key={row.slot}>
                    <td>{slotStatName(row.slot)}</td>
                    <td>{row.posts}</td>
                    <td>{row.issues}</td>
                    <td>${row.estimated_usd.toFixed(2)}</td>
                    <td>
                      {row.usd_per_issue == null
                        ? "—"
                        : `$${row.usd_per_issue.toFixed(2)}`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
          <table className="ingest-table">
            <caption>산업별 글과 그중에서 카드가 된 이슈입니다.</caption>
            <thead>
              <tr>
                <th>산업</th>
                <th>글</th>
                <th>이슈</th>
                <th>비용</th>
              </tr>
            </thead>
            <tbody>
              {stats.industries.map((row) => (
                <tr key={row.industry}>
                  <td>{row.label}</td>
                  <td>
                    {row.posts}
                    <small>
                      한 {row.korea_posts} · 영 {row.global_posts}
                    </small>
                  </td>
                  <td>
                    {row.issues}
                    {row.updates ? <small>갱신 {row.updates}</small> : null}
                  </td>
                  <td>${row.estimated_usd.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {stats.hot.length ? (
            <ul className="ingest-hot">
              {stats.hot.map((item) => (
                <li key={`${item.industry}:${item.lane}`}>
                  <strong>
                    {industryLabel[item.industry] ?? item.industry} ·{" "}
                    {laneText(item.lane)}
                  </strong>
                  <span>
                    조용한 확인 {item.idle}회
                    {item.until ? ` · ${item.until}까지` : ""}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="ingest-status">지금 추가로 감시 중인 산업은 없습니다.</p>
          )}
        </>
      ) : null}
    </section>
  );
}
