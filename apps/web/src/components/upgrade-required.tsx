import { Lock } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

/**
 * Shown in place of a gated module's content when a standard-tier user reaches
 * a Premium-only page directly. The feature isn't hidden — it's surfaced as an
 * upsell so the user knows it exists.
 */
export function UpgradeRequired({
  feature,
  description,
}: {
  feature: string;
  description?: string;
}) {
  return (
    <div className="mx-auto flex min-h-[60vh] max-w-lg items-center justify-center">
      <Card className="w-full text-center">
        <CardHeader>
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-muted">
            <Lock className="h-6 w-6 text-muted-foreground" />
          </div>
          <div className="flex items-center justify-center gap-2">
            <CardTitle>{feature}</CardTitle>
            <Badge>Premium</Badge>
          </div>
          <CardDescription>
            {description ??
              `${feature} is available on the Premium plan.`}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <p>
            Upgrade to Premium to unlock this module. Your account plan is set
            by an administrator — contact your admin to upgrade.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
