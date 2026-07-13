import { SiteFooter } from "./_components/site";
import CineNav from "./_components/nav/CineNav";
import SceneRoot from "./_components/scene/SceneRoot";
import HeroCine from "./_components/marketing/HeroCine";
import Narrative from "./_components/marketing/Narrative";
import HomeSections from "./_components/marketing/HomeSections";
import ScrollController from "./_components/scroll/ScrollController";

export default function Home() {
  return (
    <>
      <SceneRoot />
      <CineNav />
      <ScrollController />
      <main className="home-shell" id="main-content">
        <HeroCine />

        <Narrative />

        <HomeSections />
      </main>
      <SiteFooter />
    </>
  );
}
