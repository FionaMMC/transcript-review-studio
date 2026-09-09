import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Transcript Review Studio',
  description: 'A private, local-first workspace for producing and verifying research transcripts.',
  icons: { icon: '/logo.svg' },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
