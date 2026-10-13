import { getRequestConfig } from "next-intl/server";
export const locales = ["en", "vi"] as const;
export default getRequestConfig(async ({ requestLocale }) => {
  const requested = await requestLocale;
  const locale = locales.includes(requested as (typeof locales)[number])
    ? (requested as string)
    : "en";
  return {
    locale,
    timeZone: "UTC",
    messages: (await import(`../../messages/${locale}.json`)).default,
  };
});
