/**
 * Wiadomości do administratora serwisu — reached from the sidebar row
 * 'Klikam w to co trzeba / ale coś mi nie pasuje'. Placeholder until the
 * ticket form + conversation view land; the full design (form fields,
 * statuses, superuser inbox, notifications) is in
 * plans/261013-support-tickets/plan.md.
 */
export function SupportMessagesPage() {
  return (
    <div className="refined-page animate-fade-up">
      <header className="page-header">
        <div>
          <h1 className="page-title">Wiadomości do administratora serwisu</h1>
          <p className="page-subtitle">Zgłoszenia błędów i inne wiadomości na temat aplikacji</p>
        </div>
      </header>

      <section className="refined-card empty-state">
        <p className="empty-text">
          Już niedługo napiszesz tu do nas w kilka sekund — jak na Messengerze.
          <br />
          Na razie, jeśli coś nie działa, daj znać osobie, która zarządza salonem.
        </p>
      </section>
    </div>
  );
}
