"use client";

import { useApi } from "@/lib/hooks";
import type { Product } from "@/lib/types-setup";
import { ListTable } from "@/components/setup/ListTable";
import type { ListField } from "@/components/setup/ListTable";

const CODE: ListField = { key: "code", label: "Code", mode: "create", required: true };
const NAME: ListField = { key: "name", label: "Name", mode: "both", required: true };
const NAME_BN: ListField = { key: "name_bn", label: "Name (Bangla)", mode: "both" };

export function ListsTab({ canEdit }: { canEdit: boolean }) {
  const products = useApi<Product[]>("/products?limit=2000");
  const productOptions = (products.data ?? []).map((p) => ({ value: String(p.id), label: `${p.name} (${p.code})` }));
  const productName = (id: unknown) => products.data?.find((p) => p.id === id)?.name ?? String(id);

  return (
    <div className="flex flex-col gap-5">
      <ListTable title="Machine types" id="types-h" path="/catalog/machine-types" canEdit={canEdit} fields={[CODE, NAME, NAME_BN]} />
      <ListTable title="Machine brands" id="brands-h" path="/catalog/machine-brands" canEdit={canEdit} fields={[NAME]} />
      <ListTable title="Products" id="products-h" path="/products" canEdit={canEdit} fields={[CODE, NAME]} />
      <ListTable
        title="Operations"
        id="ops-h"
        path="/operations"
        canEdit={canEdit}
        fields={[
          { key: "product_id", label: "Product", mode: "create", required: true, options: productOptions, show: (r) => productName(r.product_id) },
          CODE,
          NAME,
          NAME_BN,
          { key: "smv", label: "SMV (minutes)", mode: "both", required: true, type: "number", step: "0.001" },
          { key: "difficulty_group", label: "Difficulty group", mode: "both", required: true },
        ]}
      />
      <ListTable
        title="Reason codes"
        id="reasons-h"
        path="/catalog/reason-codes"
        canEdit={canEdit}
        fields={[
          {
            key: "category",
            label: "Category",
            mode: "create",
            required: true,
            options: [
              { value: "downtime", label: "Downtime" },
              { value: "pause", label: "Pause" },
              { value: "reject", label: "Reject" },
            ],
          },
          CODE,
          NAME,
          NAME_BN,
        ]}
      />
    </div>
  );
}
