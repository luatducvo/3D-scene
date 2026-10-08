import "./globals.css";

export const metadata = { title: "S3D", description: "Local 3D scene explorer" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
