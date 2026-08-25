import { ArrowLeft } from 'lucide-react';
import { useEffect, type ReactNode } from 'react';
import { CuraiLogo } from './CuraiLogo';

type LegalDocument = 'privacy' | 'terms';

const LAST_UPDATED = 'July 24, 2026';

function PageShell({ title, children }: { title: string; children: ReactNode }) {
  return (
    <main className="classic-font min-h-[100dvh] bg-[var(--ui-bg)] px-4 py-10 text-[var(--phosphor)] sm:px-6">
      <article className="mx-auto max-w-3xl">
        <a
          href="/"
          className="mb-8 inline-flex items-center gap-2 text-sm text-[var(--phosphor-dim)] transition hover:text-[var(--phosphor-bright)]"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden />
          Back to CurieAI
        </a>
        <header className="mb-8 flex items-center gap-3 border-b border-[var(--ui-border)] pb-6">
          <CuraiLogo state="idle" size={42} />
          <div>
            <div className="type-eyebrow">CurieAI legal</div>
            <h1 className="font-display text-3xl font-semibold tracking-tight text-[var(--phosphor-bright)]">
              {title}
            </h1>
            <p className="mt-1 text-xs text-[var(--phosphor-dim)]">Last updated {LAST_UPDATED}</p>
          </div>
        </header>
        <div className="legal-copy space-y-8 text-[15px] leading-7 text-[var(--ui-text-secondary)]">
          {children}
        </div>
        <footer className="mt-12 flex flex-wrap gap-x-5 gap-y-2 border-t border-[var(--ui-border)] pt-6 text-sm text-[var(--phosphor-dim)]">
          <a className="hover:text-[var(--phosphor-bright)]" href="/privacy">Privacy</a>
          <a className="hover:text-[var(--phosphor-bright)]" href="/terms">Terms</a>
          <a className="hover:text-[var(--phosphor-bright)]" href="mailto:hello@cura-i.com">hello@cura-i.com</a>
          <a className="hover:text-[var(--phosphor-bright)]" href="https://cura-i.com">cura-i.com</a>
        </footer>
      </article>
    </main>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h2 className="mb-2 font-display text-xl font-semibold text-[var(--phosphor-bright)]">{title}</h2>
      {children}
    </section>
  );
}

function PrivacyPolicy() {
  return (
    <PageShell title="Privacy Policy">
      <p>
        CurieAI is a personal AI assistant provided through cura-i.com and app.cura-i.com. This policy
        explains what information CurieAI processes, why it is used, and the choices available to you.
      </p>

      <Section title="Information we process">
        <ul className="list-disc space-y-2 pl-6">
          <li>Account information supplied by Google Sign-In, such as your email, name, and Google account identifier.</li>
          <li>Prompts, conversations, uploaded documents, and feedback you choose to provide.</li>
          <li>Operational data such as request times, model usage, errors, security events, and basic device/browser data.</li>
          <li>Configuration and preferences needed to operate your account and selected AI features.</li>
        </ul>
      </Section>

      <Section title="How we use information">
        <p>
          We use this information to authenticate you, provide and improve CurieAI, retrieve information
          you request, prevent abuse, troubleshoot failures, measure service usage, and comply with legal
          obligations. We do not sell your personal information or use your private conversations for
          advertising.
        </p>
      </Section>

      <Section title="AI and service providers">
        <p>
          Depending on the selected feature and model, prompts or relevant context may be sent to
          third-party AI, search, hosting, storage, authentication, and observability providers. These
          providers process information to deliver the requested service under their own terms and data
          processing commitments. Avoid submitting secrets or sensitive personal information you do not
          want processed by those providers.
        </p>
      </Section>

      <Section title="Storage, retention, and security">
        <p>
          CurieAI stores account-scoped conversations and documents for continuity and retrieval until you
          delete them or your account. Operational logs and backups may be retained for a limited period
          for security and recovery. We use reasonable technical and organizational safeguards, but no
          internet service can guarantee absolute security.
        </p>
      </Section>

      <Section title="Your choices and rights">
        <p>
          You can export or delete your account data from CurieAI settings. You may also request access,
          correction, deletion, or restriction where applicable. Some records may be retained when
          required for security, fraud prevention, or legal compliance.
        </p>
      </Section>

      <Section title="Children and international use">
        <p>
          CurieAI is not directed to children under 13, or the minimum digital-consent age in your
          jurisdiction. Information may be processed in countries other than your own where our service
          providers operate.
        </p>
      </Section>

      <Section title="Changes and contact">
        <p>
          We may update this policy as CurieAI changes. The date above identifies the latest version. For
          privacy questions or requests, contact{' '}
          <a className="underline underline-offset-2" href="mailto:hello@cura-i.com">
            hello@cura-i.com
          </a>
          .
        </p>
      </Section>
    </PageShell>
  );
}

function TermsOfService() {
  return (
    <PageShell title="Terms of Service">
      <p>
        These Terms govern your use of CurieAI. By accessing the service, you agree to these Terms and the
        Privacy Policy. If you do not agree, do not use CurieAI.
      </p>

      <Section title="Service and eligibility">
        <p>
          CurieAI provides AI-assisted chat, retrieval, live-data, document, and workflow features. You must
          be legally able to enter this agreement and provide accurate account information. Access may be
          invite-only or limited while the service is in development.
        </p>
      </Section>

      <Section title="Acceptable use">
        <p>You may not use CurieAI to:</p>
        <ul className="mt-2 list-disc space-y-2 pl-6">
          <li>break the law, violate another person’s rights, or facilitate fraud or abuse;</li>
          <li>gain unauthorized access to systems, accounts, data, or restricted tools;</li>
          <li>distribute malware, disrupt the service, evade safeguards, or overwhelm infrastructure;</li>
          <li>submit content you do not have the right to use; or</li>
          <li>represent AI-generated output as professionally verified when it is not.</li>
        </ul>
      </Section>

      <Section title="Your content">
        <p>
          You retain your rights in content you submit. You grant CurieAI permission to process that content
          only as needed to provide, secure, and improve the service. You are responsible for your content,
          instructions, and any decision to share generated output.
        </p>
      </Section>

      <Section title="AI output and third-party services">
        <p>
          AI output can be inaccurate, incomplete, outdated, or unsuitable. Verify important information
          independently, especially for medical, legal, financial, employment, safety, or other high-impact
          decisions. CurieAI may rely on third-party models, search tools, data sources, and hosting services;
          their availability and terms may affect the service.
        </p>
      </Section>

      <Section title="Availability and changes">
        <p>
          CurieAI is provided on an “as available” basis and may change, experience downtime, impose usage
          limits, or discontinue features without notice. We may suspend access to protect users, providers,
          or the service, or when these Terms are violated.
        </p>
      </Section>

      <Section title="Disclaimers and limitation of liability">
        <p>
          To the fullest extent permitted by law, CurieAI is provided without warranties of accuracy,
          reliability, merchantability, fitness for a particular purpose, or non-infringement. The CurieAI
          operator will not be liable for indirect, incidental, special, consequential, or punitive damages,
          or for loss of data, profits, or opportunities resulting from use of the service.
        </p>
      </Section>

      <Section title="Termination, changes, and contact">
        <p>
          You may stop using CurieAI or delete your account at any time. We may update these Terms, with the
          date above showing the current version. Questions:{' '}
          <a className="underline underline-offset-2" href="mailto:hello@cura-i.com">
            hello@cura-i.com
          </a>
          .
        </p>
      </Section>
    </PageShell>
  );
}

export function LegalPage({ document }: { document: LegalDocument }) {
  const title = document === 'privacy' ? 'Privacy Policy' : 'Terms of Service';
  useEffect(() => {
    const previousTitle = window.document.title;
    window.document.title = `${title} | CurieAI`;
    return () => {
      window.document.title = previousTitle;
    };
  }, [title]);

  return document === 'privacy' ? <PrivacyPolicy /> : <TermsOfService />;
}
