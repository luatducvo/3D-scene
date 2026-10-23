type IconName =
  | "brand"
  | "home"
  | "measure"
  | "details"
  | "info"
  | "upload";

export function DesignIcon({ name }: { name: IconName }) {
  return (
    <img
      className={`design-icon icon-${name}`}
      src={`/design/${name}.svg`}
      alt=""
      aria-hidden="true"
    />
  );
}
