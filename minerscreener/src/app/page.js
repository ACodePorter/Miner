import Chart from "@/app/ui/Chart"
import MarketBreadth from "@/app/ui/MarketBreadth";

export default function Home() {
    return (
        <main className="flex min-h-screen flex-col items-center justify-between p-24">
            <MarketBreadth />
        </main>
    );
}
