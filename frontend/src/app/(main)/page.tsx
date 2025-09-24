import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { auth } from "~/lib/auth";

export default async function HomePage() {
  const session = await auth.api.getSession({
    headers: await headers(),
  });
  if (!session) redirect("/auth/sign-in");
  return (
    <div>
      <h1>Welcome to Voxara</h1>
      <p>Your session is active.</p>
    </div>
  );
}
